"""Copy legacy Aqua Scope SQLite data into the configured SQL Server database.

Run after creating the target database, while the old SQLite file is retained:
    python scripts/migrate_sqlite_to_sqlserver.py
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session, select

from app import config
from app.models import Particle, Sample


def main() -> None:
    source_path = Path(config.SQLITE_SOURCE_PATH)
    if not source_path.exists():
        raise SystemExit(f"SQLite source not found: {source_path}")

    source_engine = create_engine(f"sqlite:///{source_path.as_posix()}")
    target_engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    SQLModel.metadata.create_all(target_engine)

    with Session(source_engine) as source, Session(target_engine) as target:
        samples = source.exec(select(Sample).order_by(Sample.id)).all()
        copied = 0
        for legacy in samples:
            exists = target.exec(
                select(Sample).where(Sample.sample_code == legacy.sample_code)
            ).first()
            if exists is not None:
                continue
            sample = Sample(
                sample_code=legacy.sample_code,
                batch_lot=legacy.batch_lot,
                device_id=legacy.device_id,
                captured_at=legacy.captured_at,
                received_at=legacy.received_at,
                particle_count=legacy.particle_count,
                image_path=legacy.image_path,
                image_width=legacy.image_width,
                image_height=legacy.image_height,
                px_per_mm=legacy.px_per_mm,
                raw_metadata_json=legacy.raw_metadata_json,
            )
            target.add(sample)
            target.flush()
            particles = source.exec(
                select(Particle)
                .where(Particle.sample_id == legacy.id)
                .order_by(Particle.blob_index)
            ).all()
            for particle in particles:
                target.add(
                    Particle(
                        sample_id=sample.id,
                        blob_index=particle.blob_index,
                        centroid_x=particle.centroid_x,
                        centroid_y=particle.centroid_y,
                        bbox_x=particle.bbox_x,
                        bbox_y=particle.bbox_y,
                        bbox_w=particle.bbox_w,
                        bbox_h=particle.bbox_h,
                        area_px=particle.area_px,
                        size_mm=particle.size_mm,
                        label=particle.label,
                        confidence=particle.confidence,
                    )
                )
            copied += 1
        target.commit()
    print(f"Copied {copied} sample(s) from {source_path} to SQL Server.")


if __name__ == "__main__":
    main()
