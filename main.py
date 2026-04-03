from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import shutil
import os

from database import SessionLocal, User, Game, Save, engine
from sqladmin import Admin, ModelView

app = FastAPI(title="PPSSPP Cloud Sync API")
os.makedirs("saves_data", exist_ok=True)

# Зависимость для БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Настройка админ-панели (доступна по адресу /admin)
admin = Admin(app, engine)

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.quota_bytes, User.used_bytes]
class GameAdmin(ModelView, model=Game):
    column_list = [Game.id, Game.title]
class SaveAdmin(ModelView, model=Save):
    column_list = [Save.id, Save.user_id, Save.game_id, Save.version, Save.updated_at]

admin.add_view(UserAdmin)
admin.add_view(GameAdmin)
admin.add_view(SaveAdmin)

def get_current_user(db: Session = Depends(get_db)):
    user = db.query(User).first()
    if not user:
        user = User(username="player1", hashed_password="fakehash")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@app.get("/sync/{game_id}/status")
def get_save_status(game_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    save = db.query(Save).filter(Save.user_id == user.id, Save.game_id == game_id).first()
    if not save:
        return {"version": 0, "file_hash": None}
    
    return {
        "version": save.version,
        "file_hash": save.file_hash,
        "updated_at": save.updated_at
    }


@app.post("/sync/{game_id}/upload")
def upload_save(game_id: str, file_hash: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    save = db.query(Save).filter(Save.user_id == user.id, Save.game_id == game_id).first()
    old_size = save.file_size if save else 0
    new_used_bytes = user.used_bytes - old_size + file_size

    if new_used_bytes > user.quota_bytes:
        raise HTTPException(status_code=413, detail="Storage quota exceeded")

    file_path = f"saves_data/{user.id}_{game_id}_{file_hash}.zip"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if save:
        if os.path.exists(save.file_path) and save.file_path != file_path:
            os.remove(save.file_path)
            
        save.file_hash = file_hash
        save.file_path = file_path
        save.file_size = file_size
        save.version += 1
        save.updated_at = datetime.utcnow()
    else:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            game = Game(id=game_id, title=f"Game {game_id}")
            db.add(game)
        
        save = Save(user_id=user.id, game_id=game_id, version=1, file_hash=file_hash, file_path=file_path, file_size=file_size)
        db.add(save)

    user.used_bytes = new_used_bytes
    db.commit()
    
    return {"message": "Save uploaded successfully", "version": save.version}


@app.get("/sync/{game_id}/download")
def download_save(game_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    save = db.query(Save).filter(Save.user_id == user.id, Save.game_id == game_id).first()
    if not save or not os.path.exists(save.file_path):
        raise HTTPException(status_code=404, detail="Save not found")
    
    return FileResponse(path=save.file_path, filename=f"{game_id}_save.zip", media_type="application/zip")
