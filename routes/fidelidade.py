import re
import secrets

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from psycopg2 import errors

from database import conectar, criar_cursor
from services.fidelidade_service import resgatar_recompensa


_SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def _gerente_empresa():
    return session.get('nivel') == 'gerente' and session.get('empresa_id')


def _csrf():
    if not session.get('_fidelidade_csrf'):
        session['_fidelidade_csrf'] = secrets.token_urlsafe(32)
    return session['_fidelidade_csrf']


def _validar_csrf():
    recebido = request.form.get('csrf_token', '')
    guardado = session.get('_fidelidade_csrf', '')
    if not recebido or not guardado or not secrets.compare_digest(recebido, guardado):
        abort(400, description='Token de formulário inválido. Atualize a página e tente novamente.')


def registrar_rotas_fidelidade(app):
    @app.route('/fidelidade', methods=['GET', 'POST'])
    def fidelidade_gerenciar():
        if not _gerente_empresa():
            return redirect('/')

        if request.method == 'POST':
            _validar_csrf()

        empresa_id = int(session['empresa_id'])
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            if request.method == 'POST':
                nome = request.form.get('nome', '').strip()[:120]
                slug = request.form.get('slug', '').strip().lower()[:80]
                premio = request.form.get('premio', '').strip()[:500]
                try:
                    prazo = int(request.form.get('prazo_dias', ''))
                    meta = int(request.form.get('checkins_meta', ''))
                except (TypeError, ValueError):
                    flash('Prazo e quantidade de check-ins precisam ser números.', 'erro')
                    return redirect(url_for('fidelidade_gerenciar'))

                if not nome or not premio or not _SLUG.fullmatch(slug):
                    flash('Preencha o nome, prêmio e um link curto válido (letras minúsculas, números e hífens).', 'erro')
                    return redirect(url_for('fidelidade_gerenciar'))
                if not (1 <= prazo <= 3650) or not (1 <= meta <= 10000):
                    flash('O prazo deve ser de 1 a 3650 dias e a meta de 1 a 10000 check-ins.', 'erro')
                    return redirect(url_for('fidelidade_gerenciar'))

                cursor.execute(
                    'UPDATE fidelidade_campanhas SET ativa = FALSE WHERE empresa_id = %s AND ativa = TRUE',
                    (empresa_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO fidelidade_campanhas
                        (empresa_id, nome, slug, prazo_dias, checkins_meta, premio, ativa)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    """,
                    (empresa_id, nome, slug, prazo, meta, premio),
                )
                conn.commit()
                flash('Campanha criada e ativada.', 'sucesso')
                return redirect(url_for('fidelidade_gerenciar'))

            cursor.execute(
                """
                SELECT id, nome, slug, prazo_dias, checkins_meta, premio, ativa, criado_em,
                       criado_em + (prazo_dias * INTERVAL '1 day') AS expira_em,
                       (ativa AND criado_em + (prazo_dias * INTERVAL '1 day') > CURRENT_TIMESTAMP) AS vigente
                FROM fidelidade_campanhas
                WHERE empresa_id = %s
                ORDER BY criado_em DESC, id DESC
                LIMIT 20
                """,
                (empresa_id,),
            )
            campanhas = cursor.fetchall()
            cursor.execute(
                """
                SELECT r.id, r.cliente_id, c.nome AS cliente_nome,
                       f.nome AS campanha_nome, f.premio, r.ciclo, r.status,
                       r.criada_em, r.resgatada_em
                FROM fidelidade_recompensas r
                JOIN clientes c ON c.id = r.cliente_id AND c.empresa_id = r.empresa_id
                JOIN fidelidade_campanhas f ON f.id = r.campanha_id AND f.empresa_id = r.empresa_id
                WHERE r.empresa_id = %s
                ORDER BY r.criada_em DESC, r.id DESC
                LIMIT 200
                """,
                (empresa_id,),
            )
            recompensas = cursor.fetchall()
            return render_template(
                'fidelidade_gerenciar.html',
                campanhas=campanhas,
                recompensas=recompensas,
                csrf_token=_csrf(),
                url_publica=request.url_root.rstrip('/') + url_for('fidelidade_publica', slug='LINK'),
            )
        except errors.UniqueViolation:
            conn.rollback()
            flash('Esse link já está em uso. Escolha outro link curto.', 'erro')
            return redirect(url_for('fidelidade_gerenciar'))
        except Exception:
            conn.rollback()
            current_app.logger.exception('Erro no módulo de fidelidade.')
            flash('Não foi possível concluir a operação de fidelidade.', 'erro')
            return redirect(url_for('fidelidade_gerenciar'))
        finally:
            cursor.close()
            conn.close()

    @app.post('/fidelidade/recompensas/<int:recompensa_id>/resgatar')
    def fidelidade_resgatar(recompensa_id):
        if not _gerente_empresa():
            return redirect('/')
        _validar_csrf()
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            ok = resgatar_recompensa(cursor, int(session['empresa_id']), recompensa_id)
            if not ok:
                conn.rollback()
                flash('Recompensa indisponível ou progresso insuficiente para resgate.', 'erro')
            else:
                conn.commit()
                flash('Recompensa marcada como resgatada.', 'sucesso')
        except Exception:
            conn.rollback()
            current_app.logger.exception('Erro ao resgatar recompensa %s.', recompensa_id)
            flash('Não foi possível resgatar a recompensa.', 'erro')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('fidelidade_gerenciar'))

    @app.get('/fidelidade/<slug>')
    def fidelidade_publica(slug):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                SELECT nome, premio, checkins_meta, criado_em,
                       criado_em + (prazo_dias * INTERVAL '1 day') AS expira_em
                FROM fidelidade_campanhas
                WHERE slug = %s AND ativa = TRUE
                  AND criado_em + (prazo_dias * INTERVAL '1 day') > CURRENT_TIMESTAMP
                LIMIT 1
                """,
                (slug,),
            )
            campanha = cursor.fetchone()
            if not campanha:
                abort(404)
            return render_template('fidelidade_publica.html', campanha=campanha)
        finally:
            cursor.close()
            conn.close()

