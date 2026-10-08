import shutil
from pathlib import Path
from sqlmodel import Session, select
from clipfarm_api.db import engine
from clipfarm_api.models import Project

def setup_demo_awaiting():
    proj_dir = Path("data/projects/demo_awaiting")
    proj_dir.mkdir(parents=True, exist_ok=True)
    
    # Copier check.png vers frame_5.jpg pour le sélecteur Facecam
    src_img = Path("data/projects/8c8cf38238/check.png")
    if src_img.exists():
        shutil.copyfile(src_img, proj_dir / "frame_5.jpg")
    else:
        # Créer une image dummy si absente
        (proj_dir / "frame_5.jpg").write_bytes(b"dummy")

    with Session(engine) as session:
        existing = session.exec(select(Project).where(Project.id == "demo_awaiting")).first()
        if existing:
            session.delete(existing)
            session.commit()
            
        proj = Project(
            id="demo_awaiting",
            title="Stream Twitch GTA VI - Gameplay Découverte",
            source_url="https://twitch.tv/videos/123456789",
            status="awaiting_cam",
            step="awaiting_cam",
            progress=0.15,
            settings_json={
                "layout": "facecam_top",
                "format": "9:16",
                "cam": None,
                "captions": "punchy",
                "min_clip_s": 30,
                "max_clip_s": 70,
            }
        )
        session.add(proj)
        session.commit()
        print("Projet demo_awaiting prêt !")

if __name__ == "__main__":
    setup_demo_awaiting()
