from sqlmodel import Session, select
from clipfarm_api.db import engine
from clipfarm_api.models import Clip, Project

def setup_fallback_clip():
    with Session(engine) as session:
        clip = session.exec(select(Clip).where(Clip.id == "8c8cf38238_1")).first()
        if clip:
            clip.layout = {
                "name": "center",
                "fmt": "9:16",
                "face_fallback": True,
                "cam": {"x": 0.05, "y": 0.05, "w": 0.2, "h": 0.2}
            }
            clip.title = "Moment d'action (Streamer absent)"
            clip.hook = "Plein écran de jeu : focus caméra désactivé"
            clip.reason = "Moment intense du gameplay sans facecam active"
            session.add(clip)
            session.commit()
            print("Clip 8c8cf38238_1 mis à jour avec face_fallback = True !")

if __name__ == "__main__":
    setup_fallback_clip()
