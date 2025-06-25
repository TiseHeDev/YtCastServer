from flask import Flask, request, render_template_string
import pychromecast
from zeroconf import Zeroconf
import yt_dlp

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8" />
<title>Chromecast YouTube Controller</title>
<style>
    body {
        background-color: #121212;
        color: #e0e0e0;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        margin: 40px auto;
        max-width: 600px;
        padding: 0 20px 40px 20px;
    }
    h2, h3 {
        color: #bb86fc;
        text-align: center;
    }
    form {
        background-color: #1f1f1f;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 0 12px #3700b3;
        margin-bottom: 20px;
    }
    label {
        display: block;
        margin-bottom: 6px;
        font-weight: 600;
        font-size: 1.1em;
    }
    input[type="url"], select {
        width: 100%;
        padding: 10px 12px;
        margin-bottom: 18px;
        border-radius: 6px;
        border: 1px solid #333;
        background-color: #2c2c2c;
        color: #e0e0e0;
        font-size: 1em;
        transition: border-color 0.3s ease;
    }
    input[type="url"]:focus, select:focus {
        outline: none;
        border-color: #bb86fc;
        box-shadow: 0 0 8px #bb86fc;
    }
    button {
        background-color: #bb86fc;
        color: #121212;
        border: none;
        padding: 12px 25px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1em;
        cursor: pointer;
        margin-right: 10px;
        transition: background-color 0.3s ease;
    }
    button:hover {
        background-color: #9b67e0;
    }
    hr {
        border: none;
        border-top: 1px solid #333;
        margin: 30px 0;
    }
    p.message {
        background-color: #2a2a2a;
        border-left: 5px solid #bb86fc;
        padding: 15px 20px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1.1em;
        max-width: 600px;
        margin: 20px auto 0 auto;
        color: #e0e0e0;
    }
</style>
</head>
<body>

<h2>Lancer une vidéo YouTube sur ta Chromecast</h2>
<form method="POST" action="/">
    <label>URL YouTube :</label>
    <input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." size="60" {% if not video_playing %}required{% endif %}>
    
    <label>Chromecast :</label>
    <select name="device" required>
        {% for name in devices %}
        <option value="{{name}}" {% if name == selected_device %}selected{% endif %}>{{name}}</option>
        {% endfor %}
    </select>
    
    <button type="submit" name="action" value="cast">Caster</button>
</form>

{% if video_playing %}
<hr>
<h3>Contrôle de la lecture sur <b>{{selected_device}}</b></h3>
<form method="POST" action="/">
    <input type="hidden" name="device" value="{{selected_device}}">
    <button type="submit" name="action" value="play">▶️ Play</button>
    <button type="submit" name="action" value="pause">⏸ Pause</button>
    <button type="submit" name="action" value="vol_up">🔊 + Volume</button>
    <button type="submit" name="action" value="vol_down">🔉 - Volume</button>
</form>
{% endif %}

{% if message %}
<p class="message">{{message|safe}}</p>
{% endif %}

</body>
</html>
'''

zeroconf_instance = Zeroconf()
chromecasts, browser = pychromecast.get_chromecasts(zeroconf_instance=zeroconf_instance, timeout=5)
cast_devices = {cc.name: cc for cc in chromecasts}

current_cast = None
current_device_name = None

@app.route("/", methods=["GET", "POST"])
def index():
    global current_cast, current_device_name
    message = ""
    video_playing = False
    selected_device = None

    if request.method == "POST":
        action = request.form.get("action")
        device_name = request.form.get("device")

        if device_name not in cast_devices:
            message = f"❌ Chromecast '{device_name}' introuvable."
            return render_template_string(HTML, devices=cast_devices.keys(), message=message, video_playing=False, selected_device=None)

        cast = cast_devices[device_name]
        cast.wait()

        if action == "cast":
            url = request.form.get("url")
            if not url:
                message = "❌ URL manquante."
            else:
                try:
                    ydl_opts = {
                        'quiet': True,
                        'format': 'best[ext=mp4]/best',
                        'noplaylist': True,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        video_url = info["url"]

                    mc = cast.media_controller
                    mc.play_media(video_url, 'video/mp4')
                    mc.block_until_active()

                    current_cast = cast
                    current_device_name = device_name
                    video_playing = True
                    selected_device = device_name
                    message = f"✅ Vidéo lancée sur <b>{device_name}</b> !"

                except Exception as e:
                    message = f"❌ Erreur : {e}"

        else:
            if current_cast is None or current_device_name != device_name:
                message = "❌ Aucun média en cours sur cette Chromecast."
            else:
                mc = current_cast.media_controller

                if action == "pause":
                    mc.pause()
                    message = "⏸ Vidéo mise en pause."
                elif action == "play":
                    mc.play()
                    message = "▶️ Lecture reprise."
                elif action == "vol_up":
                    vol = current_cast.status.volume_level
                    new_vol = min(1.0, vol + 0.1)
                    current_cast.set_volume(new_vol)
                    message = f"🔊 Volume augmenté ({int(new_vol*100)}%)."
                elif action == "vol_down":
                    vol = current_cast.status.volume_level
                    new_vol = max(0.0, vol - 0.1)
                    current_cast.set_volume(new_vol)
                    message = f"🔉 Volume baissé ({int(new_vol*100)}%)."
                else:
                    message = "❌ Action inconnue."

                video_playing = True
                selected_device = device_name

    return render_template_string(
        HTML,
        devices=cast_devices.keys(),
        message=message,
        video_playing=video_playing,
        selected_device=selected_device
    )


if __name__ == "__main__":
    print("Chromecast disponibles :", list(cast_devices.keys()))
    try:
        app.run(host="0.0.0.0", port=8080, debug=True)
    finally:
        zeroconf_instance.close()
