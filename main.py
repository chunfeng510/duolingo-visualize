from datetime import datetime
from os import environ, path
from traceback import format_exc

from pydantic import ValidationError

from src.api import(
    APIClient,
    CaptchaException,
    LoginException,
    NotFoundException,
    UnAuthorizedException,
)
from src.database import Database
from src.schema import Summary, User, DatabaseEntry
from src.synchronizer import check_database_change, sync_database_with_summaries


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%m/%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run() -> tuple[bool, bool]:
    # Initialize environment.
    base_api_url = "https://www.duolingo.com"
    username = environ.get("DUOLINGO_USERNAME")
    token = environ.get("DUOLINGO_JWT")

    # 設定檔案路徑
    progression_database_path = path.join("data", "duolingo-progress.json")
    statistics_database_path = path.join("data", "statistics.json")

    # 初始化基本物件
    api = APIClient(base_url=base_api_url)
    progression_database = Database(filename=progression_database_path)
    statistics_database = Database(filename=statistics_database_path)
    
    raw_user, raw_summary = api.fetch_data(username, token)
    
    # 轉換資料
    user = User(**raw_user)
    summaries = [
        Summary(
            **{
                **summary,
                "gainedXp": summary.get("gainedXp") or 0,
                "numSessions": summary.get("numSessions") or 0,
                "totalSessionTime": summary.get("totalSessionTime") or 0,
            }
        )
        for summary in raw_summary["summaries"]
    ]

    current_progression = progression_database.get()
    database_entries: dict[str, DatabaseEntry] = {
        **{key: DatabaseEntry(**entry) for key, entry in current_progression.items()},
        **{summaries[0].date: DatabaseEntry.create(summaries[0], user.site_streak)},
    }

    # Synchronize the database with the summaries.
    synchronized_database = sync_database_with_summaries(database_entries, summaries)

    # Check whether we have synchronized the data or not.
    is_data_changed = check_database_change(synchronized_database, database_entries)

    # Store the synchronized database in our repository.
    progression_database.set(
        {key: value.model_dump() for key, value in synchronized_database.items()}
    )

    # On the other hand, get all of the statistics of the cron run, and then immutably
    # add the current cron statistics.
    current_date = datetime.now().strftime("%Y/%m/%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    current_statistics = statistics_database.get()
    statistics_entries: dict[str, str] = {
        **current_statistics,
        **{current_date: current_time},
    }

    # Store the statistics in our repository.
    statistics_database.set(statistics_entries)

    return is_data_changed

def main() -> None:
    # 嘗試執行主程式
    log("開始執行...")
    try:
        is_data_changed = run()
        
    except ValidationError as e:
        log(
            f"Error encountered when parsing data. Potentially, a breaking API change: {error}"
        )
    except (
        CaptchaException,
        LoginException,
        NotFoundException,
        UnAuthorizedException,
    ) as error:
        log(f"{error.__class__.__name__}: {error}")
    except Exception as error:
        log(f"Unexpected Exception: {error.__class__.__name__}: {error}")
        log(format_exc())
    finally:
        log("Japanese Duolingo Visualizer script has finished running.")

if __name__ == "__main__":
    main()