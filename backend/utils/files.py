# utils/files.py
import uuid
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)
MAX_UPLOAD_MB = 50

def safe_save(upload: UploadFile, dest_dir: Path, prefix: str = "") -> Path:
    """
    Salva un file upload con un nome randomizzato sicuro (UUID).
    Valida l'estensione, la dimensione massima (50 MB) e gestisce la creazione della cartella.
    """
    if not upload.filename or not upload.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(
            status_code=400,
            detail=f"Formato file non supportato: {upload.filename}. Caricare esclusivamente file .xls o .xlsx"
        )

    # Crea cartella di destinazione
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Genera un nome sicuro con UUID per evitare collisioni o path traversal
    ext = Path(upload.filename).suffix.lower()
    safe_name = f"{prefix}{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / safe_name
    
    size = 0
    try:
        with open(dest_path, "wb") as out:
            # Leggi in chunk per evitare di sovraccaricare la memoria RAM
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    out.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Il file caricato supera la dimensione massima consentita di {MAX_UPLOAD_MB} MB"
                    )
                out.write(chunk)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        dest_path.unlink(missing_ok=True)
        logger.error("Errore durante il salvataggio del file %s: %s", upload.filename, e)
        raise HTTPException(
            status_code=500,
            detail=f"Errore interno durante il salvataggio del file: {str(e)}"
        )
        
    logger.info("File '%s' salvato con successo come '%s' (%d KB)", upload.filename, safe_name, size // 1024)
    return dest_path

def cleanup_upload(path: Path):
    """
    Cancella un file temporaneo in modo sicuro.
    """
    try:
        if path.exists():
            path.unlink()
            logger.info("File temporaneo rimosso con successo: %s", path)
    except Exception as e:
        logger.warning("Impossibile rimuovere il file temporaneo %s: %s", path, e)
