import time
import copy
import threading
import logging
from local_utils.config import read_file

DEFAULT_CGROUP_RESOURCES = [ "memory.current", "memory.swap.current" ]
CGROUPS_ROOT_PATH = "/sys/fs/cgroup"

logger = logging.getLogger("runner.cgroups")

class CGroupsMonitor:
    def __init__(self, pid : int, resources : list = DEFAULT_CGROUP_RESOURCES):
        logger.debug(f"initializing monitor for PID: {pid}")
        self._pid = pid
        self._cgroups = {}
        self._ctrls = set()
        self._req_resources = copy.deepcopy(resources)
        self._act_resources = None
        # self._cgroups = { d.split()[0]: None for d in resources }
        # self._cgroups.update({"":None})

        self._monitoring = {
            "alive": False,
            "thread": None,
            "data": {},
        }

        # self._get_process_cgroups()
        # logger.debug(f"cgroups: {self._cgroups}")
        # self._get_controllers_enabled()
        # logger.debug(f"cgroups ctrls: {self._ctrls}")
        # self._reset_values()

    def _get_process_cgroups(self):
        changed = False
        # check what cgroups are applied to the process
        cg_text =  read_file(f"/proc/{self._pid}/cgroup")
        # logger.debug(f"cgroups for PID={self._pid}: {cg_text}")
        cg_text_list = cg_text.splitlines(False)
        for c in cg_text_list:
            if c not in [ None, "" ]:
                t = c.split(":")
                if self._cgroups.get(t[1]) != t[2]:
                    changed = True
                    logger.debug(f"cgroup changed from: {self._cgroups.get(t[1])} to {t[2]}")
                self._cgroups[ t[1] ] = t[2]
        if changed:
            logger.debug(f"cgroups: {self._cgroups}")
        return changed

    def _get_controllers_enabled(self):
        # check cgroup.controllers enabled for process' cgroups
        self._ctrls = set()
        for d, c in self._cgroups.items():
            ctrls = read_file(f"{CGROUPS_ROOT_PATH}{c}/cgroup.controllers").split()
            for k in ctrls:
                self._ctrls.add(k)
        # verify resources that can be monitored
        self._act_resources = []
        for r in self._req_resources:
            d = r.split(".")
            if d[0] in self._ctrls:
                self._act_resources.append(r)
        logger.debug(f"cgroups ctrls: {self._ctrls}, actual resources: {self._act_resources}")

    def _reset_values(self):
        self._monitoring['data'] = {}
        for r in self._act_resources:
           self._monitoring['data'][r] = [] 

    def get_values(self, mode : str = "max", reset: bool = True):
        r_values = {}
        for r, d in self._monitoring['data'].items():
            r_values[r] = max(d)        # we assume mode=="max"
        logger.debug(f"cgroups.get_values: {r_values}")
        if reset:
            self._reset_values()
        return r_values
    
    def _monitor(self):
        try:
            while self._monitoring.get("alive", False):
                # update cgroups
                changed = self._get_process_cgroups()
                if changed:
                    self._get_controllers_enabled()
                    self._reset_values()
                for r in self._act_resources:
                    r_list = []
                    for ck, cv in self._cgroups.items():
                        v = int(read_file(f"{CGROUPS_ROOT_PATH}{cv}/{r}"))
                        r_list.append(v)
                    # logger.debug(f"resource: {r}, vale={r_list}")
                    self._monitoring['data'][r].append( max(r_list) )
                time.sleep(self._monitoring['interval'])
        except IOError as e:
            print(f"no process to monitor - probably ended: {e}")
        finally:
            self._monitoring["alive"] = False
            self._monitoring["thread"] = None


    def start(self, interval : float = 0.1, reset : bool = True):
        # stop thread if running
        self.stop()
        # start a new monitoring thread
        self._monitoring["interval"] = interval
        self._monitoring["alive"] = True
        self._monitoring["thread"] = threading.Thread(target=self._monitor)
        self._monitoring["thread"].start()

    def stop(self):
        # stop thread if it is running
        if self._monitoring.get("thread") is not None:
            self._monitoring["alive"] = False
            self._monitoring.get("thread").join()
            self._monitoring["thread"] = None
