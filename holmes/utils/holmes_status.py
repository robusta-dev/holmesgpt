from holmes.core.supabase_dal import SupabaseDal
from holmes.config import Config
from holmes import get_version
import logging
from holmes.common.env_vars import  CLUSTER_NAME


def update_holmes_status_in_db(dal: SupabaseDal, config: Config):
    logging.info("Updating status of holmes")
    dal.upsert_holmes_status(
        {
            "cluster_id": CLUSTER_NAME,
            "model": config.model,
            "version": get_version(),
        }
    )
