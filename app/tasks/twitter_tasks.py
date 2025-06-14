from app.tasks.celery_app import celery
from app.services.mission_service import mission_service
from app.services.twitter_service import twitter_service
from app.crud import crud_user, crud_mission
from app.db.session import get_db
from app.core.config import logger
from app.db.redis_conn import redis_connector

# Ini adalah tugas yang akan dieksekusi di background
@celery.task(name="tasks.process_pending_twitter_missions")
async def process_pending_twitter_missions_for_user(user_id_str: str):
    logger.info(f"Starting background validation for user: {user_id_str}")
    
    redis_client = redis_connector.get_redis_client()
    pending_missions_key = f"user:{user_id_str}:pending_twitter_missions"
    
    # Ambil semua misi yang antri dari Redis set
    pending_mission_ids = redis_client.smembers(pending_missions_key)
    if not pending_mission_ids:
        logger.info(f"No pending Twitter missions to validate for user {user_id_str}.")
        return

    async for db in get_db():
        user = await crud_user.get(db, id=user_id_str)
        if not user:
            logger.error(f"User {user_id_str} not found for background validation.")
            return

        # Proses setiap misi dalam antrian
        for mission_id_str_bytes in pending_mission_ids:
            mission_id_str = mission_id_str_bytes.decode('utf-8')
            mission = await crud_mission.get_by_mission_id_str(db, mission_id_str=mission_id_str)
            if not mission:
                continue

            logger.info(f"Validating mission '{mission_id_str}' for user '{user.username}'")
            is_successful = False
            
            try:
                # Logika validasi yang sudah ada
                if mission.targetTwitterUsername:
                    is_successful = await twitter_service.check_if_user_follows(user, mission.targetTwitterUsername)
                elif mission.targetTweetId:
                    # Asumsikan misi like/retweet dibedakan dari missionId_str
                    if "like" in mission.missionId_str:
                         is_successful = await twitter_service.check_if_user_liked_tweet(user, mission.targetTweetId)
                    elif "retweet" in mission.missionId_str:
                         is_successful = await twitter_service.check_if_user_retweeted_tweet(user, mission.targetTweetId)
                
                if is_successful:
                    logger.info(f"Validation SUCCESS for mission '{mission_id_str}' for user '{user.username}'")
                    # Panggil fungsi internal untuk menyelesaikan misi & beri hadiah
                    await mission_service.finalize_mission_completion(db, user, mission)
                else:
                    logger.warning(f"Validation FAILED for mission '{mission_id_str}' for user '{user.username}'")
                    # Tandai misi gagal di DB
                    await mission_service.mark_mission_as_failed(db, user.id, mission.id)

            except Exception as e:
                logger.error(f"Error validating mission {mission_id_str} for user {user.id}: {e}", exc_info=True)
                await mission_service.mark_mission_as_failed(db, user.id, mission.id)

    # Setelah semua selesai, bersihkan antrian di Redis
    redis_client.delete(pending_missions_key)
    logger.info(f"Finished background validation for user {user_id_str}. Cleared pending queue.")