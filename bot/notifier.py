import time

# Coba import winsound (Windows only)
try:
    import winsound
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False


class Notifier:
    def play_alert(self, alert_type="alert"):
        pass


class SoundNotifier(Notifier):
    def play_alert(self, alert_type="alert"):
        try:
            if IS_WINDOWS:
                if alert_type == "profit":
                    winsound.Beep(1000, 500)
                    winsound.Beep(1200, 300)
                elif alert_type == "loss":
                    winsound.Beep(400, 800)
                    winsound.Beep(300, 500)
                elif alert_type == "alert":
                    winsound.Beep(800, 300)
                    time.sleep(0.1)
                    winsound.Beep(800, 300)
            else:
                # Fallback di Linux/Cloud
                print(f"🔔 Alert triggered: {alert_type} (no sound on this OS)")
        except Exception as e:
            print(f"Sound alert tidak dapat dimainkan: {e}")
