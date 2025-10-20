import os
from local_utils.config import write_file

class SerieStatus:
    def __init__(self, filepath : str = None):
        self._completed_tests : int = 0
        self._process_ok : int = 0
        self._expe_ok : int = 0
        self._dns_tests : list = []
        self._failed_tests : list = []
        self._filepath = filepath

        if filepath not in [ None, "" ]:
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            except:
                pass    # do not do that !!!

    def _write_to_file(self):
        if self._filepath is not None:
            status_record = self.get_status()
            write_file(status_record, self._filepath)

    def get_status(self):
        status_record = {
            "completed_tests": self._completed_tests,
            "process_ok": self._process_ok,
            "expe_ok": self._expe_ok,
            "dns_tests": self._dns_tests,
            "failed_tests": self._failed_tests
        }
        return status_record

    def report_test(self, status: dict, config: dict):
        # update serie status
        self._completed_tests += 1
        if status.get("StatusCode") == 0:
            self._process_ok += 1
        if status.get("expe_status") == "success":
            self._expe_ok += 1
        else:
            # expe failed
            record = {
                "method": config["method"].get("name"),
                "dataset": config["dataset"].get("name"),
                "hostname": os.uname().nodename,
                "runner_type": config["runner"].get("type"),
                "mem_limit": config["runner"]["limits"].get("memory")
            }
            self._failed_tests.append(record)
        self._write_to_file()

    def report_dns_tests(self, n_dns: int, n_loops: int, config: dict):
        record = {
            "n_dns": n_dns,
            "n_loops": n_loops,
            "method": config["method"].get("name"),
            "dataset": config["dataset"].get("name"),
            "limits": config["runner"].get("limits")
        }
        self._dns_tests.append(record)
        self._write_to_file()