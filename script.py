from flask import Flask, request, render_template_string
import pychromecast
from zeroconf import Zeroconf
import yt_dlp
from collections import deque

app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Chromecast YouTube Controller</title>
<style>
  body { background:#121212;color:#e0e0e0;font-family:sans-serif;margin:20px auto;max-width:600px;padding:0 15px;}
  h2,h3{color:#bb86fc;text-align:center;}
  form{background:#1f1f1f;padding:20px;border-radius:12px;box-shadow:0 0 12px #3700b3;margin-bottom:20px;}
  
  /* Conteneur centré pour URL et Chromecast */
  .centered-inputs {
    display: flex;
    flex-direction: column;
    align-items: center; /* centre horizontalement */
    max-width: 400px;
    margin: 0 auto 20px auto; /* centre horizontal et marge en bas */
  }
  .centered-inputs label,
  .centered-inputs input,
  .centered-inputs select {
    width: 100%;
    margin-bottom: 12px;
    text-align: center; /* centre le texte dans les labels */
  }

  label{font-weight:600;}
  input,select{
    padding:10px;
    border-radius:6px;
    border:1px solid #333;
    background:#2c2c2c;
    color:#e0e0e0;
  }

  /* Centrer le bouton Caster */
  button[name="action"][value="cast"] {
    display: block;
    margin: 0 auto;
    background:#bb86fc;
    color:#121212;
    border:none;
    padding:12px 25px;
    border-radius:8px;
    font-weight:700;
    cursor:pointer;
  }
  button[name="action"][value="cast"]:hover {
    background:#9b67e0;
  }

  button {
    background:#bb86fc;
    color:#121212;
    border:none;
    padding:12px 25px;
    border-radius:8px;
    font-weight:700;
    cursor:pointer;
    margin:5px;
  }
  button:hover{background:#9b67e0;}
  .message{background:#2a2a2a;border-left:5px solid #bb86fc;padding:15px;border-radius:8px;font-weight:600;}
  .now {
    text-align:center;
    margin-bottom:20px;
  }
  .now img{
    max-width:100%;
    border-radius:8px;
  }
  .recommend {
    display:flex;
    flex-wrap:wrap;
    gap:15px;
    justify-content:center;
  }
  .rec-item{
    background:#1f1f1f;
    padding:10px;
    border-radius:8px;
    width:180px;
    text-align:center;
  }
  .rec-item img{
    width:100%;
    border-radius:6px;
  }
  @media(max-width:600px){
    .rec-item{width:48%}
  }
</style></head><body>

<form method="POST">

  <div class="centered-inputs">
    <label for="url">URL YouTube :</label>
    <input id="url" type="url" name="url" placeholder="https://...watch?v=..." {% if not video_playing %}required{% endif %} value="{{ current_url or '' }}">

    <label for="device">Chromecast :</label>
    <select id="device" name="device" required>
      {% for name in devices %}
      <option value="{{name}}" {% if name==selected_device %}selected{% endif %}>{{name}}</option>
      {% endfor %}
    </select>
  </div>

  <button name="action" value="cast">Caster</button>
</form>

{% if video_playing %}
<div class="now">
  <h3>En cours sur <b>{{selected_device}}</b></h3>
  <img src="{{current_thumb}}" alt="vignette">
  <p><strong>{{ current_title }}</strong></p>
  <form method="POST" style="text-align:center;">
    <input type="hidden" name="device" value="{{selected_device}}">
    <button name="action" value="pause">⏸ Pause</button>
    <button name="action" value="play">▶️ Play</button>
    <button name="action" value="vol_up">🔊 +</button>
    <button name="action" value="vol_down">🔉 -</button>
    <button name="action" value="seek_back">⏪ -30s</button>
    <button name="action" value="seek_forward">⏩ +30s</button>
  </form>
</div>
{% endif %}

{% if recommendations %}
<h3>Recommandations</h3>
<div class="recommend">
  {% for r in recommendations %}
  <div class="rec-item">
    <img src="{{r.thumbnail}}" alt="">
    <p>{{r.title}}</p>
    <form method="POST">
      <input type="hidden" name="url" value="{{r.url}}">
      <input type="hidden" name="device" value="{{selected_device or devices|list|first}}">
      <button name="action" value="cast">Caster</button>
    </form>
  </div>
  {% endfor %}
</div>
{% endif %}

{% if message %}
<p class="message">{{message|safe}}</p>
{% endif %}

</body></html>'''

# Chromecast et état global
zeroconf = Zeroconf()
chromecasts, _ = pychromecast.get_chromecasts(zeroconf_instance=zeroconf, timeout=5)
cast_devices = {cc.name: cc for cc in chromecasts}

current_cast = None
current_device_name = None
last_video_url = None
current_title = ""
current_thumb = ""
current_url = ""

cast_history = deque(maxlen=10)  # Historique des derniers casts

@app.route("/", methods=["GET", "POST"])
def index():
    global current_cast, current_device_name, last_video_url, current_title, current_thumb, current_url
    message = ""
    video_playing = current_cast is not None
    selected = current_device_name

    recommendations = []

    if request.method == "POST":
        action = request.form.get("action")
        dev = request.form.get("device")
        if dev not in cast_devices:
            message = "❌ Chromecast introuvable."
        else:
            cast = cast_devices[dev]
            cast.wait()
            mc = cast.media_controller
            mc.block_until_active()
            if action == "cast":
                url = request.form.get("url")
                if url:
                    try:
                        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            video_url = info['url']
                            title = info.get('title')
                            thumb = info.get('thumbnail')
                        if cast == current_cast and video_url == last_video_url and mc.status.content_id == video_url:
                            message = "⚠️ Vidéo déjà en cours."
                        else:
                            mc.play_media(video_url, 'video/mp4')
                            mc.block_until_active()
                            current_cast, current_device_name = cast, dev
                            last_video_url, current_title, current_thumb = video_url, title, thumb
                            current_url = url
                            cast_history.append(url)  # Ajout à l'historique
                            message = f"✅ Play sur {dev}"
                            video_playing, selected = True, dev
                    except Exception as e:
                        message = f"❌ Erreur : {e}"
            else:
                if current_cast == cast:
                    if action == "pause":
                        mc.pause()
                        message = "⏸ Pause"
                    elif action == "play":
                        mc.play()
                        message = "▶️ Reprise"
                    elif action == "vol_up":
                        vol = min(1, cast.status.volume_level + 0.1)
                        cast.set_volume(vol)
                        message = f"🔊 {int(vol * 100)}%"
                    elif action == "vol_down":
                        vol = max(0, cast.status.volume_level - 0.1)
                        cast.set_volume(vol)
                        message = f"🔉 {int(vol * 100)}%"
                    elif action == "seek_forward":
                        new_pos = mc.status.current_time + 30
                        mc.seek(new_pos)
                        message = f"⏩ +30s"
                    elif action == "seek_back":
                        new_pos = max(0, mc.status.current_time - 30)
                        mc.seek(new_pos)
                        message = f"⏪ -30s"
                    video_playing, selected = True, dev
                else:
                    message = "❌ Diffusion non active sur cet appareil."

    if cast_history:
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                for past_url in reversed(cast_history):
                    info = ydl.extract_info(past_url, download=False)
                    related = info.get("related_videos", [])[:3]
                    for r in related:
                        video_id = r.get("url")
                        if video_id:
                            full_url = f"https://www.youtube.com/watch?v={video_id}"
                            if full_url != current_url and full_url not in cast_history:
                                recommendations.append({
                                    'url': full_url,
                                    'title': r.get('title', 'Vidéo recommandée'),
                                    'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                                })
                    if len(recommendations) >= 6:
                        break
        except Exception as e:
            print("Erreur lors du chargement des recommandations historiques :", e)

    return render_template_string(HTML,
        devices=cast_devices.keys(),
        message=message,
        video_playing=video_playing,
        selected_device=selected,
        current_title=current_title,
        current_thumb=current_thumb,
        current_url=current_url,
        recommendations=recommendations
    )

if __name__ == "__main__":
    print("Chromecasts:", list(cast_devices.keys()))
    try:
        app.run(host="0.0.0.0", port=8080)
    finally:
        zeroconf.close()
