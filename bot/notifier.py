import winsound
import time

class Notifier:
    def play_alert(self, alert_type="alert"):
        pass

class SoundNotifier(Notifier):
    def play_alert(self, alert_type="alert"):
        try:
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
        except:
            print("Sound alert tidak dapat dimainkan")
