import signal
import time


def long_running_method():
    try:
        print("start")
        time.sleep(2)
        print("inter")
        time.sleep(4)
        print("end")
    except Exception as e:
        print(f"except: {str(e)}")


def alarm_handler(signum, frame):
    raise TimeoutError(f"Process timeout expired (signal={signum})")

if __name__ == '__main__':

    old_alarm_handler = signal.signal(signal.SIGALRM, alarm_handler)

    try:
        long_running_method()
    except TimeoutError as e:
        print(e.with_traceback())

    signal.signal(signal.SIGALRM, old_alarm_handler)