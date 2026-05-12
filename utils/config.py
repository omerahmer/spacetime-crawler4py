import re


class Config(object):
    def __init__(self, config):
        self.user_agent = config["IDENTIFICATION"]["USERAGENT"].strip()
        print (self.user_agent)
        assert self.user_agent != "DEFAULT AGENT", "Set useragent in config.ini"
        assert re.match(r"^[a-zA-Z0-9_ ,]+$", self.user_agent), "User agent should not have any special characters outside '_', ',' and 'space'"
        # Multithreaded crawler: cap at 4 threads (course / politeness spec).
        self.threads_count = min(
            max(1, int(config["LOCAL PROPERTIES"]["THREADCOUNT"])), 4
        )
        self.save_file = config["LOCAL PROPERTIES"]["SAVE"]

        self.host = config["CONNECTION"]["HOST"]
        self.port = int(config["CONNECTION"]["PORT"])

        self.seed_urls = config["CRAWLER"]["SEEDURL"].split(",")
        self.time_delay = float(config["CRAWLER"]["POLITENESS"])

        self.cache_server = None