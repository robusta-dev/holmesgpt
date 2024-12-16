from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes import get_version
import logging


def update_holmes_status_in_db(dal: SupabaseDal, config: Config):
    logging.info("Updating status of holmes")
    dal.upsert_holmes_status(
        {
            "cluster_id": config.cluster_name,
            "model": config.model,
            "version": get_version(),
        }
    )
