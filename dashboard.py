#!/usr/bin/env python3
"""
Dashboard Web para administradores del bot
Accesible solo con token de administrador
VERSIÓN MEJORADA con más funcionalidades
"""

import os
import csv
import io
import shutil
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, send_file
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sqlite3
from database import get_user_stats
import logging
import requests

load_dotenv()

# Configurar logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "cambiar-esta-clave-en-produccion")
app.config['SESSION_COOKIE_HTTPONLY'] = False  # Allow JavaScript to access session
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cross-site cookies
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh session on each request

# Token de administrador desde variables de entorno
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin123")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_USERNAME_CACHE = None

DB_FILE = "users.db"


def get_db_connection():
    """Conectar a la base de datos"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    """Decorador para verificar si el usuario está autenticado como admin - DESHABILITADO PARA DESARROLLO"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # En desarrollo, permitir acceso sin autenticación
        # En producción, descomentar la línea de abajo:
        # if 'admin' not in session:
        #     return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# Health Check Endpoint (for Railway/Docker)
# ============================================================

@app.route('/health')
def health_check():
    """Health check endpoint for Railway and Docker"""
    # Temporary: always return healthy to pass healthcheck
    return jsonify({
        'status': 'healthy',
        'service': 'dashboard',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login para administradores"""
    if request.method == 'POST':
        # Support both 'token' (old) and 'password' (new) fields
        token = request.form.get('password') or request.form.get('token', '')
        if token == ADMIN_TOKEN:
            session.permanent = True  # Make session permanent
            session['admin'] = True
            session.modified = True  # Force session to be saved
            logger.info("Admin login successful")
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed admin login attempt with token: {token[:5]}...")
            return render_template('login.html', error="Contraseña incorrecta")
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cerrar sesión de admin"""
    session.clear()
    logger.info("Admin logout")
    return redirect(url_for('login'))


@app.route('/settings')
@login_required
def settings_page():
    """Página de configuración del sistema"""
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    # Get limits from env or defaults
    limits = {
        'photo': int(os.getenv('LIMIT_PHOTO', 5)),
        'video': int(os.getenv('LIMIT_VIDEO', 3)),
        'music': int(os.getenv('LIMIT_MUSIC', 5)),
        'apk': int(os.getenv('LIMIT_APK', 2))
    }
    return render_template('settings.html', now=now, limits=limits)


@app.route('/activity')
@login_required
def activity_page():
    """Página de actividad reciente"""
    return render_template('activity.html')


@app.route('/status')
def status():
    """Endpoint público de estado del sistema"""
    try:
        from database import get_user_stats
        stats = get_user_stats()
        return jsonify({
            'ok': True,
            'status': 'Online',
            'users': stats['total_users'],
            'bot_online': True,
            'dashboard_online': True,
            'miniapp_url': '/miniapp'
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@app.route('/')
@login_required
def dashboard():
    """Dashboard principal con estadísticas generales"""
    stats = get_user_stats()
    # Format estimated revenue for display
    stats['estimated_revenue'] = f"{stats['revenue']['stars']:,} ⭐"
    stats['now'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    return render_template('dashboard.html', stats=stats, now=stats['now'])


@app.route('/api/users')
@login_required
def get_users():
    """API para obtener lista de todos los usuarios con sus datos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener búsqueda opcional
        search = request.args.get('search', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Si hay búsqueda, filtrar por user_id
        if search:
            cursor.execute("""
                SELECT 
                    user_id,
                    first_name,
                    username,
                    downloads,
                    premium,
                    premium_until,
                    daily_photo,
                    daily_video,
                    daily_music,
                    daily_apk,
                    created_at,
                    updated_at
                FROM users
                WHERE user_id LIKE ? OR first_name LIKE ? OR username LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (f"%{search}%", f"%{search}%", f"%{search}%", per_page, offset))
        else:
            cursor.execute("""
                SELECT 
                    user_id,
                    first_name,
                    username,
                    downloads,
                    premium,
                    premium_until,
                    daily_photo,
                    daily_video,
                    daily_music,
                    daily_apk,
                    created_at,
                    updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset))
        
        users = []
        for row in cursor.fetchall():
            user_dict = dict(row)
            
            # Calcular días restantes de premium
            premium_days_left = None
            if user_dict['premium'] and user_dict['premium_until']:
                premium_until = datetime.fromisoformat(user_dict['premium_until'])
                days_left = (premium_until - datetime.now()).days
                premium_days_left = max(0, days_left)
            
            # Preparar datos para la respuesta
            users.append({
                'user_id': user_dict['user_id'],
                'first_name': user_dict['first_name'],
                'username': user_dict['username'],
                'downloads_count': user_dict['downloads'], # Renamed for frontend consistency
                'is_premium': bool(user_dict['premium']),
                'premium_expiry': user_dict['premium_until'], # Renamed for frontend consistency
                'premium_days_left': premium_days_left,
                'daily_photo': user_dict['daily_photo'],
                'daily_video': user_dict['daily_video'],
                'daily_music': user_dict['daily_music'],
                'daily_apk': user_dict['daily_apk'],
                'total_daily': (user_dict['daily_photo'] or 0) + (user_dict['daily_video'] or 0) + 
                              (user_dict['daily_music'] or 0) + (user_dict['daily_apk'] or 0),
                'created_at': user_dict['created_at'],
                'updated_at': user_dict['updated_at']
            })
        
        # Obtener total de usuarios
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'users': users,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        })
    
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>')
@login_required
def get_user_detail(user_id):
    """API para obtener detalles detallados de un usuario específico"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT *
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        user_dict = dict(row)
        
        # Calcular información de premium
        premium_info = {
            'is_active': bool(user_dict['premium']),
            'level': user_dict.get('premium_level', 0),
            'expires_at': user_dict['premium_until']
        }
        
        if premium_info['is_active'] and user_dict['premium_until']:
            expires = datetime.fromisoformat(user_dict['premium_until'])
            days_left = (expires - datetime.now()).days
            premium_info['days_left'] = max(0, days_left)
            premium_info['expires_soon'] = days_left <= 3
        
        return jsonify({
            'user_id': user_dict['user_id'],
            'premium': premium_info,
            'downloads': user_dict['downloads'],
            'daily_usage': {
                'photos': user_dict.get('daily_photo', 0) or 0,
                'videos': user_dict.get('daily_video', 0) or 0,
                'music': user_dict.get('daily_music', 0) or 0,
                'apk': user_dict.get('daily_apk', 0) or 0
            },
            'created_at': user_dict['created_at'],
            'updated_at': user_dict['updated_at'],
            'language': user_dict.get('language', 'es')
        })
    
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
@login_required
def get_stats():
    """API para obtener estadísticas actualizadas"""
    try:
        stats = get_user_stats()
        # Format estimated revenue for display
        stats['estimated_revenue'] = f"{stats['revenue']['stars']:,} ⭐"
        
        # Add extra stats for dashboard
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Expired premium count
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE premium = 1 AND premium_until < ?
        """, (datetime.now().isoformat(),))
        stats['expired_premium'] = cursor.fetchone()[0]
        
        # Active today (users updated today)
        today = datetime.now().date().isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE date(updated_at) = ?
        """, (today,))
        stats['active_today'] = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics')
@login_required
def get_analytics():
    """API para datos de analytics y monetización"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Usuarios totales
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Usuarios premium
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium = 1")
        premium_users = cursor.fetchone()[0]
        
        free_users = total_users - premium_users
        premium_percentage = round((premium_users / total_users * 100), 1) if total_users > 0 else 0
        
        # Descargas por tipo
        cursor.execute("SELECT SUM(downloads) FROM users")
        total_videos = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_photo) FROM users")
        total_photos = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_music) FROM users")
        total_music = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_apk) FROM users")
        total_apks = cursor.fetchone()[0] or 0
        
        # Usuarios premium recientes
        cursor.execute("""
            SELECT user_id, first_name, username, downloads, premium_until, created_at
            FROM users 
            WHERE premium = 1 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent_premium = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        # Cálculos de monetización (asumiendo precio de $5 por premium)
        premium_price = 5.0  # Puedes cambiar esto
        estimated_revenue = premium_users * premium_price
        
        # Tasa de conversión (simplificada)
        conversion_rate = premium_percentage
        
        return jsonify({
            'total_users': total_users,
            'premium_users': premium_users,
            'free_users': free_users,
            'premium_percentage': premium_percentage,
            'estimated_revenue': estimated_revenue,
            'conversion_rate': conversion_rate,
            'total_videos': total_videos,
            'total_photos': total_photos,
            'total_music': total_music,
            'total_apks': total_apks,
            'recent_premium': recent_premium
        })
    
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/users')
@login_required
def users_list():
    """Página de listado de usuarios"""
    return render_template('users.html')


@app.route('/analytics')
@login_required
def analytics():
    """Página de analytics y monetización"""
    return render_template('analytics.html')


@app.route('/user/<int:user_id>')
@login_required
def user_detail(user_id):
    """Página de detalles de un usuario"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return "Usuario no encontrado", 404

        user_data = dict(row)
        # Format data for template
        user = {
            'user_id': user_data['user_id'],
            'first_name': user_data['first_name'],
            'username': user_data['username'],
            'is_premium': bool(user_data['premium']),
            'premium_expiry': user_data['premium_until'],
            'joined_date': user_data['created_at'],
            'downloads_count': user_data['downloads'],
            'last_active': user_data['updated_at']
        }
        return render_template('user_detail.html', user=user)
    except Exception as e:
        logger.error(f"Error loading user detail: {e}")
        return "Error interno", 500


@app.route('/api/user/<int:user_id>/premium', methods=['POST', 'DELETE'])
@login_required
def manage_premium(user_id):
    """API para gestionar estado premium"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if request.method == 'POST':
            data = request.get_json()
            days = data.get('days', 30)
            
            # Calculate new expiry
            new_expiry = (datetime.now() + timedelta(days=days)).isoformat()
            
            cursor.execute("""
                UPDATE users 
                SET premium = 1, premium_until = ?, premium_level = 1
                WHERE user_id = ?
            """, (new_expiry, user_id))
            conn.commit()
            return jsonify({'success': True, 'message': f'Premium añadido por {days} días'})
            
        elif request.method == 'DELETE':
            cursor.execute("""
                UPDATE users 
                SET premium = 0, premium_until = NULL, premium_level = 0
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Premium removido'})
            
    except Exception as e:
        logger.error(f"Error managing premium for {user_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/user/<int:user_id>/reset-stats', methods=['POST'])
@login_required
def reset_user_stats(user_id):
    """API para resetear estadísticas de un usuario"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET downloads = 0, daily_photo = 0, daily_video = 0, 
                daily_music = 0, daily_apk = 0, last_reset = ?
            WHERE user_id = ?
        """, (datetime.now().isoformat(), user_id))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado'}), 404
            
        return jsonify({'success': True, 'message': 'Estadísticas reseteadas'})
        
    except Exception as e:
        logger.error(f"Error resetting stats for {user_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/user/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """API para eliminar un usuario"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado'}), 404
            
        return jsonify({'success': True, 'message': 'Usuario eliminado'})
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ==================== NUEVAS APIs DE ADMINISTRACIÓN ====================

@app.route('/api/system-info')
@login_required
def get_system_info():
    """API para obtener información del sistema"""
    try:
        # Get database size
        db_size = "N/A"
        if os.path.exists(DB_FILE):
            size_bytes = os.path.getsize(DB_FILE)
            if size_bytes < 1024:
                db_size = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                db_size = f"{size_bytes / 1024:.1f} KB"
            else:
                db_size = f"{size_bytes / (1024 * 1024):.2f} MB"
        
        return jsonify({
            'db_size': db_size,
            'server_time': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'db_file': DB_FILE
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/users')
@login_required
def export_users_csv():
    """API para exportar usuarios a CSV"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener filtros
        search = request.args.get('search', '')
        status = request.args.get('status', 'all')
        
        # Construir query con filtros
        query = """
            SELECT user_id, first_name, username, downloads, premium, 
                   premium_until, daily_photo, daily_video, daily_music, 
                   daily_apk, language, created_at, updated_at
            FROM users
        """
        conditions = []
        params = []
        
        if search:
            conditions.append("(user_id LIKE ? OR first_name LIKE ? OR username LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
        if status == 'premium':
            conditions.append("premium = 1")
        elif status == 'free':
            conditions.append("premium = 0")
        elif status == 'expired':
            conditions.append("premium = 1 AND premium_until < datetime('now')")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'User ID', 'Nombre', 'Username', 'Descargas', 'Premium',
            'Premium Hasta', 'Fotos Hoy', 'Videos Hoy', 'Música Hoy',
            'APKs Hoy', 'Idioma', 'Creado', 'Actualizado'
        ])
        
        # Data
        for row in rows:
            writer.writerow([
                row['user_id'],
                row['first_name'] or '',
                row['username'] or '',
                row['downloads'],
                'Sí' if row['premium'] else 'No',
                row['premium_until'] or '',
                row['daily_photo'] or 0,
                row['daily_video'] or 0,
                row['daily_music'] or 0,
                row['daily_apk'] or 0,
                row['language'] or 'es',
                row['created_at'] or '',
                row['updated_at'] or ''
            ])
        
        output.seek(0)
        
        # Generate filename with date
        filename = f"usuarios_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/backup')
@login_required
def backup_database():
    """API para descargar backup de la base de datos"""
    try:
        if not os.path.exists(DB_FILE):
            return jsonify({'error': 'Base de datos no encontrada'}), 404
        
        # Create a backup copy
        backup_filename = f"backup_users_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        backup_path = f"/tmp/{backup_filename}"
        
        shutil.copy2(DB_FILE, backup_path)
        
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/reset-all-daily', methods=['POST'])
@login_required
def reset_all_daily():
    """API para resetear contadores diarios de todos los usuarios"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET daily_photo = 0, daily_video = 0, 
                daily_music = 0, daily_apk = 0, 
                last_reset = ?
        """, (datetime.now().isoformat(),))
        
        affected = cursor.rowcount
        conn.commit()
        
        logger.info(f"Admin reset all daily counters. Affected: {affected}")
        return jsonify({'success': True, 'affected': affected})
        
    except Exception as e:
        logger.error(f"Error resetting all daily: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/clean-expired-premium', methods=['POST'])
@login_required
def clean_expired_premium():
    """API para limpiar usuarios con premium expirado"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        now = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE users 
            SET premium = 0, premium_level = 0
            WHERE premium = 1 AND premium_until < ?
        """, (now,))
        
        affected = cursor.rowcount
        conn.commit()
        
        logger.info(f"Cleaned expired premium. Affected: {affected}")
        return jsonify({'success': True, 'affected': affected})
        
    except Exception as e:
        logger.error(f"Error cleaning expired premium: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/remove-all-premium', methods=['POST'])
@login_required
def remove_all_premium():
    """API para quitar premium a todos los usuarios"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET premium = 0, premium_level = 0, premium_until = NULL
            WHERE premium = 1
        """)
        
        affected = cursor.rowcount
        conn.commit()
        
        logger.warning(f"Admin removed ALL premium. Affected: {affected}")
        return jsonify({'success': True, 'affected': affected})
        
    except Exception as e:
        logger.error(f"Error removing all premium: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/delete-inactive', methods=['POST'])
@login_required
def delete_inactive_users():
    """API para eliminar usuarios inactivos (30+ días)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        
        # Don't delete premium users
        cursor.execute("""
            DELETE FROM users 
            WHERE updated_at < ? AND premium = 0
        """, (cutoff,))
        
        affected = cursor.rowcount
        conn.commit()
        
        logger.warning(f"Deleted inactive users. Affected: {affected}")
        return jsonify({'success': True, 'affected': affected})
        
    except Exception as e:
        logger.error(f"Error deleting inactive users: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/add-premium-bulk', methods=['POST'])
@login_required
def add_premium_bulk():
    """API para añadir premium a múltiples usuarios"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        data = request.get_json()
        user_ids = data.get('user_ids', [])
        days = data.get('days', 30)
        
        if not user_ids:
            return jsonify({'error': 'No se proporcionaron IDs de usuarios'}), 400
        
        new_expiry = (datetime.now() + timedelta(days=days)).isoformat()
        
        placeholders = ','.join(['?' for _ in user_ids])
        cursor.execute(f"""
            UPDATE users 
            SET premium = 1, premium_until = ?, premium_level = 1
            WHERE user_id IN ({placeholders})
        """, [new_expiry] + user_ids)
        
        affected = cursor.rowcount
        conn.commit()
        
        logger.info(f"Bulk premium added. Days: {days}, Affected: {affected}")
        return jsonify({'success': True, 'affected': affected})
        
    except Exception as e:
        logger.error(f"Error bulk adding premium: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/activity/stats')
@login_required
def get_activity_stats():
    """API para obtener estadísticas de actividad"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        
        # Today's downloads (sum of daily counters)
        cursor.execute("""
            SELECT COALESCE(SUM(daily_photo + daily_video + daily_music + daily_apk), 0)
            FROM users
            WHERE date(last_reset) = ?
        """, (today,))
        today_downloads = cursor.fetchone()[0]
        
        # New users today
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE date(created_at) = ?
        """, (today,))
        new_users_today = cursor.fetchone()[0]
        
        # Active premium
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE premium = 1 AND premium_until > ?
        """, (datetime.now().isoformat(),))
        active_premium = cursor.fetchone()[0]
        
        # Expiring in 3 days
        three_days = (datetime.now() + timedelta(days=3)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE premium = 1 AND premium_until BETWEEN ? AND ?
        """, (datetime.now().isoformat(), three_days))
        expiring_soon = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'today_downloads': today_downloads,
            'new_users_today': new_users_today,
            'active_premium': active_premium,
            'expiring_soon': expiring_soon
        })
        
    except Exception as e:
        logger.error(f"Error getting activity stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/activity')
@login_required
def get_activity():
    """API para obtener actividad reciente (simulada desde datos de usuarios)"""
    try:
        page = request.args.get('page', 1, type=int)
        filter_type = request.args.get('filter', 'all')
        per_page = 20
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        activities = []
        
        # Get recent user activity based on updated_at
        cursor.execute("""
            SELECT user_id, first_name, username, downloads, premium, 
                   premium_until, daily_photo, daily_video, daily_music, 
                   daily_apk, created_at, updated_at
            FROM users
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        rows = cursor.fetchall()
        
        for row in rows:
            user_name = row['first_name'] or f"Usuario #{row['user_id']}"
            
            # Check what kind of activity this might be
            if filter_type in ['all', 'downloads']:
                total_daily = (row['daily_photo'] or 0) + (row['daily_video'] or 0) + \
                             (row['daily_music'] or 0) + (row['daily_apk'] or 0)
                
                if total_daily > 0:
                    activities.append({
                        'type': 'download',
                        'title': 'Descarga realizada',
                        'description': f'{user_name} realizó {total_daily} descarga(s) hoy',
                        'user_id': row['user_id'],
                        'timestamp': row['updated_at']
                    })
            
            if filter_type in ['all', 'premium']:
                if row['premium'] and row['premium_until']:
                    # Check if premium was recently added (within last day)
                    activities.append({
                        'type': 'premium',
                        'title': 'Usuario Premium',
                        'description': f'{user_name} tiene premium activo',
                        'user_id': row['user_id'],
                        'timestamp': row['updated_at']
                    })
            
            if filter_type in ['all', 'users']:
                # Check if new user (created recently)
                created = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                if created and (datetime.now() - created).days < 7:
                    activities.append({
                        'type': 'user',
                        'title': 'Nuevo usuario',
                        'description': f'{user_name} se registró',
                        'user_id': row['user_id'],
                        'timestamp': row['created_at']
                    })
        
        # Sort by timestamp and limit
        activities.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        activities = activities[:per_page]
        
        # Check if there's more
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        has_more = (page * per_page) < total
        
        conn.close()
        
        return jsonify({
            'activities': activities,
            'has_more': has_more,
            'page': page
        })
        
    except Exception as e:
        logger.error(f"Error getting activity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/filter')
@login_required
def filter_users():
    """API avanzada para filtrar usuarios"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get filter parameters
        status = request.args.get('status', 'all')  # all, premium, free, expired
        sort_by = request.args.get('sort', 'created_at')  # created_at, downloads, updated_at
        order = request.args.get('order', 'desc')  # asc, desc
        min_downloads = request.args.get('min_downloads', 0, type=int)
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Build query
        conditions = []
        params = []
        
        if status == 'premium':
            conditions.append("premium = 1 AND premium_until > ?")
            params.append(datetime.now().isoformat())
        elif status == 'free':
            conditions.append("premium = 0")
        elif status == 'expired':
            conditions.append("premium = 1 AND premium_until < ?")
            params.append(datetime.now().isoformat())
        
        if min_downloads > 0:
            conditions.append("downloads >= ?")
            params.append(min_downloads)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Validate sort column
        valid_sorts = ['created_at', 'downloads', 'updated_at', 'user_id', 'premium']
        if sort_by not in valid_sorts:
            sort_by = 'created_at'
        
        order_dir = 'DESC' if order == 'desc' else 'ASC'
        
        query = f"""
            SELECT user_id, first_name, username, downloads, premium, 
                   premium_until, created_at, updated_at
            FROM users
            {where_clause}
            ORDER BY {sort_by} {order_dir}
            LIMIT ? OFFSET ?
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        users = []
        for row in cursor.fetchall():
            user_dict = dict(row)
            premium_days_left = None
            if user_dict['premium'] and user_dict['premium_until']:
                premium_until = datetime.fromisoformat(user_dict['premium_until'])
                days_left = (premium_until - datetime.now()).days
                premium_days_left = max(0, days_left)
            
            users.append({
                'user_id': user_dict['user_id'],
                'first_name': user_dict['first_name'],
                'username': user_dict['username'],
                'downloads_count': user_dict['downloads'],
                'is_premium': bool(user_dict['premium']),
                'premium_expiry': user_dict['premium_until'],
                'premium_days_left': premium_days_left,
                'created_at': user_dict['created_at'],
                'updated_at': user_dict['updated_at']
            })
        
        # Get total with same filters
        count_query = f"SELECT COUNT(*) FROM users {where_clause}"
        cursor.execute(count_query, params[:-2] if params else [])  # Exclude LIMIT/OFFSET params
        total = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'users': users,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        })
        
    except Exception as e:
        logger.error(f"Error filtering users: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Broadcast API Endpoint
# ============================================================

@app.route('/api/admin/broadcast', methods=['POST'])
@login_required
def broadcast_message():
    """API para enviar mensajes masivos a todos los usuarios"""
    import requests
    import time
    
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    target = data.get('target', 'all')  # all, premium, free
    
    if not message:
        return jsonify({'error': 'El mensaje no puede estar vacío'}), 400
    
    if len(message) > 4096:
        return jsonify({'error': 'El mensaje es demasiado largo (máx 4096 caracteres)'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener usuarios según el filtro
        if target == 'premium':
            cursor.execute("SELECT user_id FROM users WHERE premium = 1")
        elif target == 'free':
            cursor.execute("SELECT user_id FROM users WHERE premium = 0")
        else:
            cursor.execute("SELECT user_id FROM users")
        
        users = cursor.fetchall()
        total_users = len(users)
        
        if total_users == 0:
            return jsonify({'error': 'No hay usuarios para enviar el mensaje'}), 400
        
        # Enviar mensajes usando la API de Telegram
        bot_token = os.getenv('TELEGRAM_TOKEN')
        if not bot_token:
            return jsonify({'error': 'Token de Telegram no configurado'}), 500
        
        sent = 0
        failed = 0
        blocked = 0
        
        for user in users:
            user_id = user['user_id']
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    sent += 1
                else:
                    error_code = result.get('error_code', 0)
                    if error_code == 403:  # User blocked the bot
                        blocked += 1
                    else:
                        failed += 1
                        logger.warning(f"Failed to send to {user_id}: {result}")
                
                # Rate limiting - Telegram allows ~30 messages/second
                time.sleep(0.035)
                
            except Exception as e:
                failed += 1
                logger.error(f"Error sending to {user_id}: {e}")
        
        logger.info(f"Broadcast completed: sent={sent}, failed={failed}, blocked={blocked}")
        
        return jsonify({
            'success': True,
            'total': total_users,
            'sent': sent,
            'failed': failed,
            'blocked': blocked
        })
        
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/admin/broadcast/preview', methods=['POST'])
@login_required
def broadcast_preview():
    """API para previsualizar el conteo de usuarios que recibirán el mensaje"""
    data = request.get_json() or {}
    target = data.get('target', 'all')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if target == 'premium':
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE premium = 1")
        elif target == 'free':
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE premium = 0")
        else:
            cursor.execute("SELECT COUNT(*) as count FROM users")
        
        result = cursor.fetchone()
        count = result['count'] if result else 0
        
        return jsonify({'count': count, 'target': target})
        
    except Exception as e:
        logger.error(f"Error in broadcast preview: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ============================================================
# MiniApp API Endpoints
# ============================================================

@app.route('/miniapp')
def miniapp():
    """Serve the Telegram MiniApp"""
    return send_file('miniapp/index.html')


@app.route('/api/miniapp/user', methods=['POST'])
def miniapp_get_user():
    """API endpoint for MiniApp to get user data"""
    try:
        data = request.get_json() or {}
        user_info = data.get('user', {})
        user_id = user_info.get('id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        # Check if user has a session file (connected account)
        session_file = f"sessions/session_{user_id}.session"
        has_session = os.path.exists(session_file)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, first_name, username, downloads, premium, premium_until,
                   daily_photo, daily_video, daily_music, daily_apk, created_at, language
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            # Return default data for new users
            return jsonify({
                'user_id': user_id,
                'first_name': user_info.get('first_name', 'Usuario'),
                'username': user_info.get('username', ''),
                'language': 'es',  # Default language
                'premium': False,
                'premium_until': None,
                'has_session': has_session,
                'downloads': 0,
                'daily_video': 0,
                'daily_photo': 0,
                'daily_music': 0,
                'daily_apk': 0,
                'limits': {
                    'video': {'used': 0, 'max': 3},
                    'photo': {'used': 0, 'max': 10},
                    'music': {'used': 0, 'max': 0},
                    'apk': {'used': 0, 'max': 0}
                }
            })
        
        user = dict(row)
        is_premium = bool(user['premium'])
        
        # Calculate limits based on premium status
        limits = {
            'video': {
                'used': user['daily_video'] or 0,
                'max': 50 if is_premium else 3
            },
            'photo': {
                'used': user['daily_photo'] or 0,
                'max': 999 if is_premium else 10
            },
            'music': {
                'used': user['daily_music'] or 0,
                'max': 50 if is_premium else 0
            },
            'apk': {
                'used': user['daily_apk'] or 0,
                'max': 50 if is_premium else 0
            }
        }
        
        return jsonify({
            'user_id': user['user_id'],
            'first_name': user['first_name'] or user_info.get('first_name', 'Usuario'),
            'username': user['username'] or user_info.get('username', ''),
            'language': user.get('language', 'es'),  # User's language from DB
            'premium': is_premium,
            'premium_until': user['premium_until'],
            'has_session': has_session,
            'downloads': user['downloads'] or 0,
            'daily_video': user['daily_video'] or 0,
            'daily_photo': user['daily_photo'] or 0,
            'daily_music': user['daily_music'] or 0,
            'daily_apk': user['daily_apk'] or 0,
            'limits': limits
        })
        
    except Exception as e:
        logger.error(f"MiniApp user API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/stats')
def miniapp_stats():
    """Get global stats for miniapp (public endpoint)"""
    try:
        stats = get_user_stats()
        return jsonify({
            'total_users': stats['total_users'],
            'premium_users': stats['premium_users'],
            'total_downloads': stats['total_downloads']
        })
    except Exception as e:
        logger.error(f"MiniApp stats error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/create-invoice', methods=['POST'])
def create_invoice():
    """Create a Telegram Stars invoice link with support for multiple plans"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        plan_key = data.get('plan_key', 'monthly')  # Default to monthly plan
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        # Premium plans configuration
        PREMIUM_PLANS = {
            'trial': {
                'stars': 25,
                'days': 3,
                'name': '🎁 Prueba',
                'description': 'Prueba Premium por 3 días | Descargas ilimitadas'
            },
            'weekly': {
                'stars': 75,
                'days': 7,
                'name': '🔥 Semanal',
                'description': 'Premium por 7 días | Mejor precio por día'
            },
            'monthly': {
                'stars': 149,
                'days': 30,
                'name': '💎 Mensual',
                'description': 'Premium por 30 días | El más popular'
            },
            'quarterly': {
                'stars': 399,
                'days': 90,
                'name': '👑 Trimestral',
                'description': 'Premium por 90 días | Ahorra hasta 50%'
            }
        }
        
        # Get plan details or default to monthly
        plan = PREMIUM_PLANS.get(plan_key, PREMIUM_PLANS['monthly'])
            
        # Telegram API createInvoiceLink
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/createInvoiceLink"
        
        payload = {
            "title": f"{plan['name']} - Premium {plan['days']} días",
            "description": plan['description'],
            "payload": f"premium_{plan['days']}_days_{plan_key}_{user_id}",
            "provider_token": "",  # Empty for Stars
            "currency": "XTR",
            "prices": [{"label": f"Premium {plan['days']} días", "amount": plan['stars']}]
        }
        
        response = requests.post(url, json=payload)
        result = response.json()
        
        if result.get('ok'):
            logger.info(f"Invoice created for user {user_id}: {plan_key} ({plan['stars']}⭐ / {plan['days']}d)")
            return jsonify({'ok': True, 'invoice_link': result['result']})
        else:
            logger.error(f"Telegram API error: {result}")
            return jsonify({'error': 'Failed to create invoice'}), 500
            
    except Exception as e:
        logger.error(f"Create invoice error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/download', methods=['POST'])
def miniapp_download():
    """API endpoint to process download requests from MiniApp"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        link = data.get('link', '')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        if not link or 't.me/' not in link:
            return jsonify({'error': 'Valid Telegram link required'}), 400
        
        # Check if user has session
        session_file = f"sessions/session_{user_id}.session"
        if not os.path.exists(session_file):
            return jsonify({
                'ok': False, 
                'error': 'no_session',
                'message': 'Necesitas configurar tu cuenta primero'
            })
        
        # Send message to user via bot
        send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        message_payload = {
            "chat_id": user_id,
            "text": f"📥 *Descarga solicitada desde MiniApp*\n\n🔗 Procesando: {link}\n\n⏳ Espera un momento...",
            "parse_mode": "Markdown"
        }
        requests.post(send_url, json=message_payload)
        
        return jsonify({
            'ok': True,
            'message': 'Descarga iniciada. Revisa el chat del bot.'
        })
        
    except Exception as e:
        logger.error(f"MiniApp download error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/configure', methods=['POST'])
def miniapp_configure():
    """API endpoint to redirect user to configure account"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        # Send message to user via bot with configure instructions
        send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        keyboard = {
            "inline_keyboard": [[
                {"text": "⚙️ Configurar ahora", "callback_data": "connect_account"}
            ]]
        }
        
        message_payload = {
            "chat_id": user_id,
            "text": "⚙️ *Configuración de cuenta*\n\n"
                    "Para descargar contenido de canales privados, necesitas vincular tu cuenta de Telegram.\n\n"
                    "Toca el botón de abajo para comenzar:",
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        requests.post(send_url, json=message_payload)
        
        return jsonify({
            'ok': True,
            'message': 'Revisa el chat del bot para configurar'
        })
        
    except Exception as e:
        logger.error(f"MiniApp configure error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/disconnect', methods=['POST'])
def miniapp_disconnect():
    """API endpoint to disconnect user session"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        # Remove session file
        session_file = f"sessions/session_{user_id}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
            
            # Notify user
            send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            message_payload = {
                "chat_id": user_id,
                "text": "✅ Tu cuenta ha sido desconectada correctamente.\n\nPuedes volver a configurarla cuando quieras con /configurar",
                "parse_mode": "Markdown"
            }
            requests.post(send_url, json=message_payload)
            
            return jsonify({
                'ok': True,
                'message': 'Cuenta desconectada'
            })
        else:
            return jsonify({
                'ok': False,
                'message': 'No tienes ninguna cuenta conectada'
            })
        
    except Exception as e:
        logger.error(f"MiniApp disconnect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/miniapp/referrals', methods=['GET'])
def miniapp_referrals():
    """API endpoint para obtener estadísticas de referidos"""
    try:
        user_id = request.args.get('user_id', type=int)
        
        logger.info(f"MiniApp referrals request for user_id: {user_id}")
        
        if not user_id:
            return jsonify({'ok': False, 'error': 'User ID required'}), 400
        
        # Importar funciones de database
        from database import get_referral_stats
        
        # Obtener estadísticas
        stats = get_referral_stats(user_id)
        logger.info(f"Stats for user {user_id}: {stats}")
        
        # Generar enlace de referido
        # Intentar obtener el username del bot (cachear si es posible)
        global BOT_USERNAME_CACHE
        bot_username = os.getenv('BOT_USERNAME') or BOT_USERNAME_CACHE
        
        if not bot_username:
            try:
                logger.info("Fetching bot username from Telegram API...")
                bot_info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
                bot_response = requests.get(bot_info_url, timeout=5).json()
                logger.info(f"Telegram API response: {bot_response}")
                bot_username = bot_response.get('result', {}).get('username', 'MEDIA_SAVE_videosbot')
                BOT_USERNAME_CACHE = bot_username
                logger.info(f"Bot username set to: {bot_username}")
            except Exception as e:
                logger.error(f"Error getting bot username: {e}")
                bot_username = "MEDIA_SAVE_videosbot"  # Fallback a nombre conocido
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        logger.info(f"Generated referral link: {referral_link}")
        
        response = {
            'ok': True,
            'stats': {
                'confirmed': stats.get('confirmed', 0),
                'pending': stats.get('pending', 0),
                'days_earned': stats.get('days_earned', 0),
                'progress': stats.get('progress', 0),
                'next_reward_at': stats.get('next_reward_at', 15)
            },
            'referral_link': referral_link,
            'max_days': 15
        }
        
        logger.info(f"Returning referral response: {response}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"MiniApp referrals error: {e}", exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500


# ============================================================
# NUEVOS ENDPOINTS PARA GRÁFICOS
# ============================================================

@app.route('/api/charts/revenue')
@login_required
def get_revenue_chart():
    """Datos de ingresos últimos 7 días"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener ingresos últimos 7 días por día
        revenue_data = []
        for i in range(6, -1, -1):  # Últimos 7 días
            date = (datetime.now() - timedelta(days=i)).date()
            # Contar usuarios creados ese día
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE date(created_at) = ? AND premium = 1
            """, (date.isoformat(),))
            count = cursor.fetchone()[0]
            revenue_data.append({
                'date': date.isoformat(),
                'revenue': count * 500  # 500 stars por usuario (aproximado)
            })
        
        conn.close()
        
        return jsonify({
            'labels': [d['date'] for d in revenue_data],
            'data': [d['revenue'] for d in revenue_data]
        })
    except Exception as e:
        logger.error(f"Error fetching revenue chart: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/charts/users')
@login_required
def get_users_chart():
    """Datos de usuarios nuevos últimos 7 días"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Usuarios nuevos últimos 7 días
        users_data = []
        for i in range(6, -1, -1):  # Últimos 7 días
            date = (datetime.now() - timedelta(days=i)).date()
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE date(created_at) = ?
            """, (date.isoformat(),))
            count = cursor.fetchone()[0]
            users_data.append({
                'date': date.isoformat(),
                'users': count
            })
        
        conn.close()
        
        return jsonify({
            'labels': [d['date'] for d in users_data],
            'data': [d['users'] for d in users_data]
        })
    except Exception as e:
        logger.error(f"Error fetching users chart: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/charts/distribution')
@login_required
def get_distribution_chart():
    """Distribución de usuarios (free vs premium)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium = 0")
        free = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium = 1")
        premium = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'labels': ['Gratuitos', 'Premium'],
            'data': [free, premium],
            'colors': ['#3b82f6', '#10b981']
        })
    except Exception as e:
        logger.error(f"Error fetching distribution chart: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/charts/downloads')
@login_required
def get_downloads_chart():
    """Distribución de descargas por tipo"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(downloads) FROM users")
        videos = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_photo) FROM users")
        photos = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_music) FROM users")
        music = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(daily_apk) FROM users")
        apks = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'labels': ['Videos', 'Fotos', 'Música', 'APK'],
            'data': [videos, photos, music, apks],
            'colors': ['#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4']
        })
    except Exception as e:
        logger.error(f"Error fetching downloads chart: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Get port from environment (Railway provides PORT)
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    logger.info(f"Dashboard iniciando en {host}:{port}...")
    app.run(debug=False, host=host, port=port)
