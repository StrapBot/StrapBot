import logging
import sys

try:
    from colorama import Fore, Style
except ImportError:
    Fore = Style = type(
        "testù" + ("ù" * 100000), (object,), {"__getattr__": lambda self, item: ""}
    )()


class StrapLog(logging.Logger):
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.lvl = logging.INFO
        self.stream = logging.StreamHandler(stream=sys.stdout)
        self.levels = {
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self.fatal = self.critical

    def configure(self, bot, level="INFO"):
        self.lvl = self.levels.get(level)
        if level is not None:
            self.lvl = level

        self.stream.setLevel(self.lvl)
        self.setLevel(self.lvl)
        self.addHandler(self.stream)

        self.bot = bot

    @staticmethod
    def _info_(*messages):
        return f'{Fore.BLUE}Info{Style.RESET_ALL}\t{" ".join(messages)}'.replace(
            "\n\n", f"\n\n{Fore.BLUE}Info{Style.RESET_ALL}\t"
        ).replace("\n", f"\n{Fore.BLUE}Info{Style.RESET_ALL}\t")

    @staticmethod
    def _debug_(*messages):
        return f'{Fore.LIGHTMAGENTA_EX}Debug{Style.RESET_ALL}\t{" ".join(messages)}'.replace(
            "\n\n", f"\n\n{Fore.LIGHTMAGENTA_EX}Debug{Style.RESET_ALL}\t"
        ).replace(
            "\n", f"\n{Fore.LIGHTMAGENTA_EX}Debug{Style.RESET_ALL}\t"
        )

    @staticmethod
    def _warning_(*messages):
        return f'{Fore.YELLOW}Warn{Style.RESET_ALL}\t{" ".join(messages)}'.replace(
            "\n\n", f"\n\n{Fore.YELLOW}Warn{Style.RESET_ALL}\t"
        ).replace("\n", f"\n{Fore.YELLOW}Warn{Style.RESET_ALL}\t")

    @staticmethod
    def _error_(*messages):
        return f'{Fore.RED}Error{Style.RESET_ALL}\t{" ".join(messages)}'.replace(
            "\n\n", f"\n\n{Fore.RED}Error{Style.RESET_ALL}\t"
        ).replace("\n", f"\n{Fore.RED}Error{Style.RESET_ALL}\t")

    @staticmethod
    def _critical_(*messages):
        if len(messages) == 1 and messages[0].lower() == "exception":
            message = "Fatal exception:"
        else:
            message = " ".join(messages)

        return (
            (
                f"{Fore.RED}"
                f'{message if message == "Fatal exception:" else "Fatal"}'
                f"{Style.RESET_ALL}\t"
                f'{message if message != "Fatal exception:" else ""}'
            )
            .replace("\n\n", f"\n\n{Fore.RED}Fatal{Style.RESET_ALL}\t")
            .replace("\n", f"\n{Fore.RED}Fatal{Style.RESET_ALL}\t")
        )

    def info(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.INFO):
            self._log(logging.INFO, self._info_(message), args, **kwargs)

    def debug(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, self._debug_(message), args, **kwargs)

    def warning(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, self._warning_(message), args, **kwargs)

    def error(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, self._error_(message), args, **kwargs)

    def critical(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, self._critical_(message), args, **kwargs)


def get_logger_instance(name="StrapBot") -> StrapLog:
    logging.setLoggerClass(StrapLog)
    logger = logging.getLogger("StrapBot")
    self = logger

    self.stream.setLevel(self.lvl)
    self.setLevel(self.lvl)
    self.addHandler(self.stream)
    return logger
