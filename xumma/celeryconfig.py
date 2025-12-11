import os
import dotenv

env_file = os.path.join(os.path.dirname(
    os.path.dirname(os.path.realpath(__file__))), '.env')
dotenv.load_dotenv(env_file)

REDIS_HOST = os.getenv('REDIS_HOST')

broker_url = f"redis://{REDIS_HOST}:6379/1"
result_backend = f"redis://{REDIS_HOST}:6379/2"
broker_connection_retry_on_startup = True

broker_connection_retry_on_startup = True

task_track_started = True
task_time_limit = 30 * 60
result_extended = True
task_acks_late = True
task_reject_on_worker_lost = True
task_ignore_result = False
result_expires = 3600  # 1 hour
