#!/usr/bin/env python3
import os
import re

FILE_PATH = "miniapp/index.html"

with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

parts = content.split("    <script>", 1)
if len(parts) != 2:
    parts = content.split("<script>", 1)

old_js = parts[1]
# We only want the content inside the tag.
if "</script>" in old_js:
    old_js = old_js.split("</script>", 1)[0]


# REPLACEMENTS PARA LOGICA (Referidos y Planes)
old_js = old_js.replace("s.days_earned", "s.downloads_earned")

NEW_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>DownloadBot</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="miniapp/translations.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Nunito:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --void: #040912;
            --deep: #070D1B;
            --surface: #0C1526;
            --card: #111E32;
            --card-hi: #16263F;
            --line: rgba(255,183,0,0.08);
            --gold: #FFB700;
            --gold-dim: rgba(255,183,0,0.18);
            --gold-glow: rgba(255,183,0,0.35);
            --cyan: #00D4FF;
            --cyan-dim: rgba(0,212,255,0.14);
            --emerald: #10D9A0;
            --rose: #FF5E7A;
            --violet: #A855F7;
            --txt: #EEF2F8;
            --txt-soft: #8899B8;
            --txt-muted: #4A5878;
            --r: 16px;
            --rs: 10px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        
        body {
            font-family: 'Nunito', sans-serif;
            background: var(--void);
            color: var(--txt);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            position: relative;
        }

        /* Ambient Glow & Grain */
        body::before {
            content: '';
            position: fixed;
            top: -20%;
            left: -10%;
            width: 120%;
            height: 120%;
            background: radial-gradient(circle at 50% 0%, var(--gold-dim) 0%, transparent 60%);
            z-index: -2;
            pointer-events: none;
        }
        body::after {
            content: '';
            position: fixed;
            inset: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.04'/%3E%3C/svg%3E");
            z-index: -1;
            pointer-events: none;
        }

        h1, h2, h3, .syne, .price, .stat-value { font-family: 'Syne', sans-serif; }

        /* HEADER */
        .header {
            position: sticky;
            top: 0;
            z-index: 50;
            background: rgba(4, 9, 18, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--line);
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .app-brand { display: flex; align-items: center; gap: 12px; }
        .app-logo {
            width: 36px; height: 36px; border-radius: 12px;
            background: linear-gradient(135deg, var(--gold), #D97706);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px; box-shadow: 0 0 15px var(--gold-glow);
        }
        .app-name { font-size: 18px; font-weight: 800; color: #FFF; letter-spacing: 0.5px; }
        
        .user-chip {
            background: var(--card); border: 1px solid var(--line);
            padding: 4px 12px 4px 4px; border-radius: 20px;
            display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600;
        }
        .user-avatar {
            width: 24px; height: 24px; border-radius: 50%;
            background: var(--card-hi); display: flex; align-items: center; justify-content: center;
            color: var(--gold); font-weight: bold;
        }

        /* CONTAINER */
        .container { flex: 1; padding: 20px; padding-bottom: 100px; display: flex; flex-direction: column; gap: 20px; }
        
        /* TABS */
        .tab-panel { display: none; opacity: 0; transition: opacity 0.4s ease;  }
        .tab-panel.active { display: block; animation: fadeIn 0.4s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* CARDS */
        .card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: var(--r);
            padding: 20px;
            position: relative;
            overflow: hidden;
        }
        .card-gold { background: linear-gradient(145deg, var(--card), #1B2910); border-color: var(--gold-dim); }

        .sec-label { font-size: 12px; font-weight: 800; text-transform: uppercase; color: var(--gold); letter-spacing: 1px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }

        /* INPUTS & BUTTONS */
        .input-box {
            background: rgba(0,0,0,0.3); border: 1px solid var(--line); border-radius: var(--rs);
            padding: 16px; width: 100%; color: #FFF; font-family: 'Nunito'; font-size: 15px; outline: none; transition: 0.3s;
        }
        .input-box:focus { border-color: var(--gold); box-shadow: 0 0 0 3px var(--gold-dim); }
        
        .btn {
            width: 100%; padding: 16px; border: none; border-radius: var(--rs);
            font-family: 'Syne'; font-weight: 700; font-size: 15px; cursor: pointer;
            transition: 0.3s; display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .btn:active { transform: scale(0.97); }
        .btn-gold { background: linear-gradient(135deg, var(--gold), #D97706); color: #000; box-shadow: 0 4px 15px var(--gold-glow); }
        .btn-outline { background: transparent; border: 1px solid var(--gold); color: var(--gold); }
        .btn-cyan { background: linear-gradient(135deg, var(--cyan), #0284C7); color: #FFF; box-shadow: 0 4px 15px var(--cyan-dim); }

        /* CREDITS BAR */
        .credits-bar { background: rgba(0,0,0,0.5); border-radius: 30px; height: 12px; width: 100%; overflow: hidden; margin-top: 10px; }
        .credits-fill { background: linear-gradient(90deg, var(--gold), #FDE047); height: 100%; width: 0%; border-radius: 30px; transition: 1s cubic-bezier(0.1, 0.8, 0.2, 1); }

        /* LOCKED STATE */
        .locked-block { text-align: center; padding: 30px 10px; }
        .locked-icon { font-size: 48px; margin-bottom: 16px; filter: drop-shadow(0 0 10px var(--gold-glow)); }

        /* PREMIUM PLANS */
        .plan-grid { display: flex; flex-direction: column; gap: 12px; }
        .plan-card {
            background: var(--card-hi); border: 1px solid var(--line); border-radius: var(--r);
            padding: 20px; display: flex; align-items: center; justify-content: space-between;
            transition: 0.3s; cursor: pointer;
        }
        .plan-card:active { transform: scale(0.98); }
        .plan-card.pro { border-color: var(--gold); background: linear-gradient(145deg, var(--card-hi), rgba(255,183,0,0.05)); }
        .plan-badge { font-size: 10px; font-weight: 800; background: var(--gold); color: #000; padding: 4px 8px; border-radius: 12px; margin-bottom: 6px; display: inline-block;}
        .plan-price-star { font-size: 18px; margin-left: 2px; }

        /* GUIE FAQ */
        .faq-item { border-bottom: 1px solid var(--line); }
        .faq-q { display:flex; justify-content:space-between; padding:14px 16px; cursor:pointer; font-weight: 600; font-size: 15px; color: var(--txt); }
        .faq-q-icon { font-family:'Syne'; transition: transform .25s; color: var(--gold); font-size: 18px; line-height: 1; }
        .faq-item.open .faq-q-icon { transform: rotate(45deg); }
        .faq-a { max-height:0; overflow:hidden; transition: max-height .35s ease, padding .25s; padding:0 16px; font-size:13px; color: var(--txt-soft); line-height: 1.6; }
        .faq-item.open .faq-a { max-height:400px; padding:0 16px 14px; }

        ol.guide-steps { padding-left: 20px; display:flex; flex-direction:column; gap:12px; color: var(--txt-soft); font-size: 14px; margin: 0; }
        ol.guide-steps li strong { color: var(--txt); }
        
        .chip-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .chip { background: var(--card-hi); border: 1px solid var(--line); border-radius: 20px; padding: 6px 14px; font-size: 12px; color: var(--txt-soft); }

        /* ACCOUNT MENU */
        .ami { display: flex; align-items: center; gap: 16px; padding: 16px 0; border-bottom: 1px solid var(--line); cursor: pointer; }
        .ami:last-child { border-bottom: none; }
        .ami-icon { width: 40px; height: 40px; border-radius: 12px; background: var(--card-hi); display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--gold); }
        .ami-text { flex: 1; }
        .ami-title { font-size: 15px; font-weight: 600; color: var(--txt); }
        .ami-sub { font-size: 12px; color: var(--txt-muted); margin-top: 2px; }
        .ami-arrow { color: var(--txt-muted); font-size: 20px; }

        /* BOTTOM NAV */
        .nav {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: rgba(4, 9, 18, 0.7); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-top: 1px solid var(--line); display: flex; justify-content: space-around;
            padding: 10px; z-index: 50; padding-bottom: calc(10px + env(safe-area-inset-bottom));
        }
        .nav-btn {
            background: transparent; border: none; color: var(--txt-muted);
            display: flex; flex-direction: column; align-items: center; gap: 4px;
            font-family: 'Nunito'; font-size: 11px; font-weight: 600; cursor: pointer; transition: 0.3s;
            width: 20%; flex-shrink: 0;
        }
        .nav-icon { font-size: 20px; transition: 0.3s; margin-bottom: 2px; filter: grayscale(1); opacity: 0.7;}
        .nav-btn.active { color: var(--gold); }
        .nav-btn.active .nav-icon { filter: grayscale(0); opacity: 1; transform: translateY(-2px) scale(1.1); filter: drop-shadow(0 2px 4px var(--gold-glow)); }
        
        #toast {
            position: fixed; top: 80px; left: 50%; transform: translateX(-50%) translateY(-20px);
            background: var(--card-hi); border: 1px solid var(--line); color: #FFF;
            padding: 12px 24px; border-radius: 30px; font-size: 13px; font-weight: 600;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); opacity: 0; pointer-events: none; transition: 0.3s; z-index: 9999;
        }
        #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
        
        #loading { position: fixed; inset: 0; background: var(--void); display: flex; align-items: center; justify-content: center; z-index: 9000; }
        .spinner { width: 40px; height: 40px; border: 3px solid var(--line); border-top-color: var(--gold); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

    </style>
</head>
<body>

    <div id="loading"><div class="spinner"></div></div>

    <div id="toast"></div>

    <header class="header">
        <div class="app-brand">
            <div class="app-logo">⚜️</div>
            <div class="app-name">DownloadBot</div>
        </div>
        <div class="user-chip" id="connBtn" onclick="isConnected ? disconnectAccount() : configureAccount()">
            <div class="user-avatar" id="userAvatar">U</div>
            <span id="userName">Usuario</span>
            <span id="connIcon" style="font-size: 10px; margin-left: 4px;">⛔</span>
        </div>
    </header>

    <div class="container" id="app" style="display: none;">
        
        <!-- INICIO TAB -->
        <div id="tab-home" class="tab-panel active">
            <div class="card" style="padding-bottom: 24px;">
                <h2 style="font-size: 24px; font-weight: 800; margin-bottom: 8px;">Descarga Mágica</h2>
                <p style="color: var(--txt-soft); font-size: 14px; margin-bottom: 20px;">Obtén cualquier archivo de canales privados al instante.</p>
                
                <div id="creditsBlock">
                    <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700;">
                        <span style="color:var(--txt-soft);">Descargas Disponibles</span>
                        <span id="creditsCountText" style="color:var(--gold);">0</span>
                    </div>
                    <div class="credits-bar">
                        <div class="credits-fill" id="creditsFill"></div>
                    </div>
                    <div style="margin-top:24px;" id="downloadArea">
                        <input type="text" id="linkInput" class="input-box" placeholder="https://t.me/c/12345/678" style="margin-bottom: 12px;">
                        <button class="btn btn-gold" id="downloadBtn" onclick="startDownload()">
                            <span>⚡ Procesar Enlace</span>
                        </button>
                    </div>
                </div>

                <div id="lockedBlock" class="locked-block" style="display:none;">
                    <div class="locked-icon">🔒</div>
                    <h3 style="font-size: 18px; margin-bottom: 8px; color: var(--rose);">Sin descargas disponibles</h3>
                    <p style="font-size: 13px; color: var(--txt-soft); margin-bottom: 24px; line-height: 1.5;">Para seguir descargando contenido exclusivo, necesitas recargar tus descargas.</p>
                    <div style="display:flex; flex-direction:column; gap:12px;">
                        <button class="btn btn-gold" onclick="switchTab('premium')">💎 Ver Planes Premium</button>
                        <button class="btn btn-outline" onclick="switchTab('referrals')" style="border-color:var(--cyan); color:var(--cyan);">👥 Obtener Gratis (Invitar)</button>
                    </div>
                </div>
            </div>

            <!-- History UI (kept simple) -->
            <div id="historyCard" class="card" style="display:none; padding: 0;">
                <div style="padding: 16px 20px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between;">
                    <span class="sec-label" style="margin:0;">Últimas Descargas</span>
                </div>
                <div id="historyList"></div>
            </div>
        </div>

        <!-- PREMIUM TAB -->
        <div id="tab-premium" class="tab-panel">
            <div class="sec-label">🌟 Status</div>
            <div class="card card-gold" style="text-align:center;">
                <div style="font-size:40px; margin-bottom:12px;">👑</div>
                <div id="premiumStatus" style="font-size:18px; font-weight:700; color:var(--gold); margin-bottom:4px;">Cuenta Gratuita</div>
                <div id="userPlan" style="font-size:13px; color:var(--txt-soft);">Sin suscripción activa</div>
            </div>

            <div class="sec-label" style="margin-top: 24px;">💎 Planes VIP</div>
            <div class="plan-grid">
                <!-- Flash (Hidden by default, will be controlled by JS if needed, or removed as per user prompt we rely on basic/pro/elite only now) -->
                
                <!-- Basic -->
                <div class="plan-card" onclick="buyPremium('basic')">
                    <div>
                        <div class="plan-badge" style="background:var(--txt-muted); color:#FFF;">INICIAL</div>
                        <div style="font-family:'Syne'; font-size:20px; font-weight:700; color:var(--txt);">Básico <span style="font-size:14px; color:var(--txt-muted); font-weight:500;">/ 7 días</span></div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'Syne'; font-size:24px; font-weight:800; color:var(--gold);">333⭐</div>
                    </div>
                </div>
                <!-- Pro -->
                <div class="plan-card pro" onclick="buyPremium('pro')">
                    <div>
                        <div class="plan-badge">🔥 RECOMENDADO</div>
                        <div style="font-family:'Syne'; font-size:20px; font-weight:700; color:var(--txt);">Pro <span style="font-size:14px; color:var(--txt-muted); font-weight:500;">/ 30 días</span></div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'Syne'; font-size:24px; font-weight:800; color:var(--gold);">777⭐</div>
                    </div>
                </div>
                <!-- Elite -->
                <div class="plan-card" onclick="buyPremium('elite')">
                    <div>
                        <div class="plan-badge" style="background:var(--emerald); color:#000;">MÁXIMO PODER</div>
                        <div style="font-family:'Syne'; font-size:20px; font-weight:700; color:var(--txt);">Elite <span style="font-size:14px; color:var(--txt-muted); font-weight:500;">/ 90 días</span></div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'Syne'; font-size:24px; font-weight:800; color:var(--gold);">1499⭐</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- REFERRALS TAB -->
        <div id="tab-referrals" class="tab-panel">
            <div class="card" style="text-align:center; padding: 30px 20px;">
                <div style="font-size:48px; margin-bottom:16px;">🎁</div>
                <h2 style="font-size:22px; font-weight:800; margin-bottom:8px;">Gana Descargas</h2>
                <!-- Cada 15 refs = 10 descargas -->
                <p style="color:var(--txt-soft); font-size:14px; line-height:1.5;">Invita a 15 amigos a iniciar el bot y recibe 10 descargas gratis inmediatamente.</p>
                
                <div style="background:var(--bg-input); border-radius:var(--rs); padding:16px; margin-top:24px;">
                    <div style="font-family:'Syne'; font-size:32px; font-weight:800; color:var(--cyan); margin-bottom:4px;" id="refProgressText">0/15</div>
                    <div style="font-size:12px; color:var(--txt-muted); text-transform:uppercase; letter-spacing:1px; font-weight:700;">Progreso actual</div>
                </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                <div class="card" style="margin:0; padding:16px; display:flex; flex-direction:column; align-items:center;">
                    <div style="color:var(--txt-soft); font-size:11px; text-transform:uppercase; font-weight:700; margin-bottom:8px;">Totales</div>
                    <div style="font-family:'Syne'; font-size:24px; font-weight:800; color:var(--txt);" id="refConfirmed">0</div>
                </div>
                <div class="card" style="margin:0; padding:16px; display:flex; flex-direction:column; align-items:center;">
                    <!-- 'Ganadas' -->
                    <div style="color:var(--txt-soft); font-size:11px; text-transform:uppercase; font-weight:700; margin-bottom:8px;">Ganadas</div>
                    <div style="font-family:'Syne'; font-size:24px; font-weight:800; color:var(--emerald);" id="refEarned">0</div>
                </div>
            </div>

            <button class="btn btn-cyan" onclick="shareReferralLink()">
                <span style="font-size:18px;">🔗</span> Compartir Enlace
            </button>
        </div>

        <!-- GUIDE TAB -->
        <div id="tab-guide" class="tab-panel">
            <div class="card" style="text-align:center; background:linear-gradient(180deg, rgba(255,183,0,0.1) 0%, var(--card) 100%); padding-top: 30px; padding-bottom: 30px;">
                <div style="font-size:48px; margin-bottom:12px;">📖</div>
                <h2 style="font-size:24px; font-weight:800; color:var(--gold);">Guía Completa</h2>
                <p style="color:var(--txt-soft); font-size:14px; margin-top:8px;">Todo lo que necesitas saber para dominar el bot.</p>
            </div>

            <div class="sec-label" style="margin-top:24px;">¿Qué es DownloadBot?</div>
            <div class="card">
                <p style="color:var(--txt-soft); font-size:14px; line-height:1.6;">Somos tu pasarela para extraer contenido restringido de Telegram. Archivos que no se pueden guardar, reenviar o descargar de canales privados ahora están a tu alcance.</p>
                <div class="chip-wrap">
                    <div class="chip">📹 Videos</div><div class="chip">📸 Fotos</div><div class="chip">🎵 Música</div><div class="chip">📦 APKs</div><div class="chip">📚 Álbumes</div>
                </div>
            </div>

            <div class="sec-label" style="margin-top:24px;">Cómo empezar</div>
            <div class="card">
                <ol class="guide-steps">
                    <li>Ve a la pestaña <strong>Cuenta</strong> y toca "Configurar de nuevo" si no lo has hecho.</li>
                    <li>Sigue las instrucciones en el chat y <strong>recibe tu código de acceso</strong> oficial.</li>
                    <li>Ingresa el código en el bot para conectar tu cuenta de forma <strong>segura</strong>.</li>
                    <li>Copia el enlace de cualquier mensaje de un canal privado al que pertenezcas.</li>
                    <li>Pega el enlace en la pestaña <strong>Inicio</strong> y recibe el archivo descargable.</li>
                </ol>
            </div>

            <div class="sec-label" style="margin-top:24px;">Formatos de enlace válidos</div>
            <div class="card">
                <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
                    <div style="background:var(--card-hi); padding:10px 12px; border-radius:8px; font-family:monospace; font-size:13px; color:var(--txt);">t.me/nombrecanal/123 <span style="float:right; color:var(--txt-muted); font-family:'Nunito';">Canal público</span></div>
                    <div style="background:var(--card-hi); padding:10px 12px; border-radius:8px; font-family:monospace; font-size:13px; color:var(--cyan);">t.me/c/1234567890/456 <span style="float:right; opacity:0.8; font-family:'Nunito';">Canal privado</span></div>
                    <div style="background:var(--card-hi); padding:10px 12px; border-radius:8px; font-family:monospace; font-size:13px; color:var(--txt);">t.me/+ABCxyz123/789 <span style="float:right; color:var(--txt-muted); font-family:'Nunito';">Grupo</span></div>
                </div>
                <div style="background:var(--gold-dim); border:1px solid var(--gold); padding:10px 12px; border-radius:8px; font-size:12px; color:var(--gold);">
                    💡 <strong>Tip:</strong> Si estás en Android, toca el mensaje y usa "Copiar Enlace".
                </div>
            </div>

            <div class="sec-label" style="margin-top:24px;">¿Cómo consigo descargas?</div>
            <div style="display:flex; flex-direction:column; gap:12px;">
                <div class="card" style="border-color:var(--cyan); background:linear-gradient(135deg, var(--card), rgba(0,212,255,0.05));">
                    <h4 style="color:var(--cyan); font-size:15px; font-weight:700; margin-bottom:6px;">👥 Invitando Amigos</h4>
                    <p style="color:var(--txt-soft); font-size:13px; line-height:1.5;">Recomienda a tus referidos. Cada 15 usuarios que inicien el bot a través de tu enlace, recibirás 10 descargas gratis inmediatamente y de forma automática.</p>
                </div>
                <div class="card" style="border-color:var(--gold); background:linear-gradient(135deg, var(--card), rgba(255,183,0,0.05));">
                    <h4 style="color:var(--gold); font-size:15px; font-weight:700; margin-bottom:6px;">💎 Adquiriendo Premium</h4>
                    <p style="color:var(--txt-soft); font-size:13px; line-height:1.5;">Elige tranquilidad. Descargas ILIMITADAS sin cortes ni demoras. Contamos con membresías Premium a partir de 333⭐ por mes.</p>
                </div>
            </div>

            <div class="sec-label" style="margin-top:24px;">Preguntas Frecuentes</div>
            <div class="card" style="padding:0;">
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Es seguro conectar mi cuenta?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">Totalmente. El túnel de inicio de sesión usa una conexión segura de Telegram. No leemos ni interactuamos con tus chats personales o ajenos al enlace proporcionado.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Por qué mi descarga está tardando?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">La carga de archivos gigantes puede tardar. Los usuarios Premium siempre saltarán la cola y tendrán prioridad de procesamiento de velocidad.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Referidos pendientes no suman?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">Se marcan en verde apenas inicien al menos por vez primera el bot. Usuarios falsos o bots se descartan.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿De qué canales puedo extraer?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">De cualquiera. Al aportar tu autorización segura en Cuenta, puedes invocar material restringido de canales públicos o privados a los que tú estés unido.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Qué son las Telegram Stars?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">Son la moneda hiper segura oficial de Telegram. Evitan salir de tu App para pagar y admiten Google Pay/Apple Pay.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Baja la calidad del archivo?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">Negativo. Enviamos en crudo tal cual el archivo host original sin comprimir un solo bit.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Hay renovación automática?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">No hay cobros recurrentes sorpresivos. Recargarás tus días estrella tan solo si tú lo confirmas manualmente cada mes.</div>
                </div>
                <div class="faq-item">
                    <div class="faq-q" onclick="toggleFaq(this)"><span>¿Aún necesitas ayuda soporte?</span><span class="faq-q-icon">+</span></div>
                    <div class="faq-a">Puedes ir tranquilamente a la pestaña "Cuenta" y presionar Centro de Soporte para comunicarte en privado con el Staff en Telegram.</div>
                </div>
            </div>

            <div class="sec-label" style="margin-top:24px;">Consejos útiles</div>
            <div class="card">
                <div style="display:flex; flex-direction:column; gap:12px; font-size:13px; color:var(--txt-soft);">
                    <div style="display:flex; gap:10px;"><span style="color:var(--gold);">⚡</span> Copia, Pega, Envía rápido, la memoria retiene el caché para que descargues en lotes ágiles.</div>
                    <div style="display:flex; gap:10px;"><span style="color:var(--gold);">🎯</span> Usa el cliente Telegram Desktop para copiar lotes masivos más sencillo.</div>
                    <div style="display:flex; gap:10px;"><span style="color:var(--gold);">✨</span> Comprueba cuánta fecha te queda en Configuración periódicamente.</div>
                    <div style="display:flex; gap:10px;"><span style="color:var(--gold);">🚀</span> Comparte tu referido entre alumnos o en redes TikTok con un video tutorial del bot para ganancias ilimitadas.</div>
                </div>
            </div>

            <button class="btn btn-outline" onclick="openSupport()" style="margin-top:16px; margin-bottom: 20px;">💬 Contactar Soporte Técnico</button>
        </div>

        <!-- PROFILE TAB -->
        <div id="tab-profile" class="tab-panel">
            <div class="sec-label">Tu Cuenta</div>
            <div class="card">
                <div class="ami" onclick="switchTab('guide')">
                    <span class="ami-icon">📖</span>
                    <div class="ami-text">
                        <div class="ami-title">Guía de uso</div>
                        <div class="ami-sub">Cómo usar el bot paso a paso</div>
                    </div>
                    <span class="ami-arrow">›</span>
                </div>
                <div class="ami" id="connBtn" onclick="isConnected ? disconnectAccount() : configureAccount()">
                    <span class="ami-icon" id="connIcon">🔌</span>
                    <div class="ami-text">
                        <div class="ami-title" id="connTitle">Estado de la cuenta</div>
                        <div class="ami-sub" id="connSub">Verificando...</div>
                    </div>
                    <span class="ami-arrow">›</span>
                </div>
                <div class="ami" onclick="openSupport()">
                    <span class="ami-icon">💬</span>
                    <div class="ami-text">
                        <div class="ami-title">Centro de soporte</div>
                        <div class="ami-sub">Resolución de problemas</div>
                    </div>
                    <span class="ami-arrow">›</span>
                </div>
                <div class="ami" onclick="switchTab('referrals')" style="border:none;">
                    <span class="ami-icon">🎁</span>
                    <div class="ami-text">
                        <div class="ami-title">Referidos</div>
                        <div class="ami-sub">Gana descargas gratis</div>
                    </div>
                    <span class="ami-arrow">›</span>
                </div>
            </div>
            
            <div style="text-align:center; font-size:11px; color:var(--txt-muted); margin-top:20px;">
                DownloadBot v3.0 Luxury<br>Dark Edition
            </div>
        </div>
    </div>

    <!-- BOTTOM NAV -->
    <nav class="nav" id="bottomNav" style="display: none;">
        <button class="nav-btn active" id="nav-home" onclick="switchTab('home')">
            <span class="nav-icon">⬇</span><span>Inicio</span>
        </button>
        <button class="nav-btn" id="nav-premium" onclick="switchTab('premium')">
            <span class="nav-icon">⭐</span><span>Premium</span>
        </button>
        <button class="nav-btn" id="nav-referrals" onclick="switchTab('referrals')">
            <span class="nav-icon">👥</span><span>Referidos</span>
        </button>
        <button class="nav-btn" id="nav-guide" onclick="switchTab('guide')">
            <span class="nav-icon">📖</span><span>Guía</span>
        </button>
        <button class="nav-btn" id="nav-profile" onclick="switchTab('profile')">
            <span class="nav-icon">👤</span><span>Cuenta</span>
        </button>
    </nav>
"""

new_js = """
window.toggleFaq = function(qEl) {
    const item = qEl.parentElement;
    const wasOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
    if (!wasOpen) item.classList.add('open');
};

const originalUpdateUI = window.updateUI || function(){};
window.updateUI = function() {
    originalUpdateUI();
    
    // Update Connection visual
    const icon = document.getElementById('connIcon');
    if (icon && typeof isConnected !== 'undefined') {
        icon.textContent = isConnected ? '✅' : '⛔';
        const color = isConnected ? 'var(--emerald)' : 'var(--rose)';
        if(document.getElementById('connTitle')) {
            document.getElementById('connTitle').textContent = isConnected ? 'Conectado de forma segura' : 'Cuenta desconectada';
        }
    }
    
    // Credits logic without downloads free (Only Referrals or Premium)
    const creditsBlock = document.getElementById('creditsBlock');
    const lockedBlock = document.getElementById('lockedBlock');
    const creditsCountText = document.getElementById('creditsCountText');
    const creditsFill = document.getElementById('creditsFill');
    
    if (window.userData) {
        let isPremium = window.userData.premium;
        // User starts with 0 free downloads except what they earned via referrals
        let used = window.userData.downloads || 0;
        let earned = 0; // if we fetched from referrals or stored in DB... 
        
        let available = 0; // We define it manually
        // Note: the backend handles limits, we assume for basic users: max = earned
        // The user request specified: 'Si isPremium || credits > 0 mostrar el input de descarga, si no mostrar bloque locked'
        // For accurate tracking if we don't have credits via limits, we assume max value.
        // Wait, "credits" implies limits.video.max - limits.video.used or similar?
        let max_downloads = 0;
        if (userData.limits && userData.limits.video) {
            max_downloads = userData.limits.video.max || 0;
            used = userData.limits.video.used || 0;
        }
        
        available = max_downloads - used;
        if (available < 0) available = 0;

        if (isPremium || available > 0) {
            if (creditsBlock) creditsBlock.style.display = 'block';
            if (lockedBlock) lockedBlock.style.display = 'none';
            if (isPremium) {
                if (creditsCountText) creditsCountText.textContent = 'ILIMITADAS 👑';
                if (creditsFill) { creditsFill.style.width = '100%'; creditsFill.style.background = 'linear-gradient(90deg, #10D9A0, #047857)'; }
            } else {
                if (creditsCountText) creditsCountText.textContent = available;
                // Max is based on what they earned. Typically earned in blocks of 10.
                if (creditsFill) creditsFill.style.width = Math.min((used/(max_downloads))*100, 100) + '%';
            }
        } else {
            if (creditsBlock) creditsBlock.style.display = 'none';
            if (lockedBlock) lockedBlock.style.display = 'block';
        }
    }
};

window.buyPremium = async function(planKey = 'basic') {
    if(typeof showToast === 'function') showToast('Preparando pago...');
    const plans = {
        'basic': { stars: 333, days: 7, name: '🚀 Básico' },
        'pro': { stars: 777, days: 30, name: '🔥 Pro' },
        'elite': { stars: 1499, days: 90, name: '💎 Elite' }
    };
    const plan = plans[planKey] || plans['pro'];
    try {
        const response = await fetch('/api/miniapp/create-invoice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userData?.user_id || tg.initDataUnsafe?.user?.id,
                plan_key: planKey
            })
        });
        const result = await response.json();
        if (result.ok && result.invoice_link) {
            tg.openInvoice(result.invoice_link, (status) => {
                if (status === 'paid') {
                    tg.showAlert('¡Pago exitoso! Disfruta Premium.');
                    if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
                    setTimeout(() => { loadUserData(); tg.close(); }, 2000);
                } else if (status === 'cancelled') {
                    if(typeof showToast === 'function') showToast('Pago cancelado');
                } else if (status === 'failed') {
                    if(typeof showToast === 'function') showToast('Error en el pago');
                }
            });
        }
    } catch (e) {
        if(typeof showToast === 'function') showToast('Error de conexión');
    }
};

const originalSwitchTab = window.switchTab;
window.switchTab = function(tabId) {
    document.querySelectorAll('.tab-panel').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    const panel = document.getElementById('tab-' + tabId);
    const nav = document.getElementById('nav-' + tabId);
    if(panel) panel.classList.add('active');
    if(nav) nav.classList.add('active');
    
    window.scrollTo(0, 0);
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
};
"""

FINAL_HTML = f"{NEW_HTML}\n<script>\n{old_js}\n{new_js}\n</script>\n</body>\n</html>"

with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.write(FINAL_HTML)

print("✅ MiniApp HTML successfully rewritten with script injection!")
