from sqlmodel import Session, select
from .models import QcSetting
from . import config

def get_warn_particle_count(session: Session) -> int:
    """Retrieve warn_particle_count from database settings or fallback to config."""
    setting = session.exec(
        select(QcSetting).where(QcSetting.key == "warn_particle_count")
    ).first()
    if setting is None:
        return config.WARN_PARTICLE_COUNT

    try:
        value = int(setting.value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("warn_particle_count setting must be an integer") from exc
    if value < 0:
        raise RuntimeError("warn_particle_count setting must be >= 0")
    return value
