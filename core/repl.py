"""code repl and AsyncIO repl from the Python source code, modified to work with the bot."""
import ast
import sys
import code
import types
import signal
import asyncio
import inspect
import warnings
import threading
import __future__
import concurrent.futures

from functools import partial
from asyncio import futures
from typing import Optional
from .utils import get_logger

logger = get_logger("repl")


class InteractiveConsole(code.InteractiveConsole):
    INTERRUPT_MSG = "KeyboardInterrupt caught. Press enter to get back in the REPL."

    def __init__(self, locals, bot, loop: asyncio.AbstractEventLoop):
        super().__init__(locals)
        self.compile.compiler.flags |= ast.PyCF_ALLOW_TOP_LEVEL_AWAIT

        from strapbot import StrapBot

        self.__running = False
        self.__more = 0
        self.__code_future = None
        self.bot: StrapBot = bot
        self.loop = loop
        self.repl_future = None
        self.repl_future_interrupted = False
        self.input_task = None
        self.sigint_pressed = False

    @property
    def running(self):
        return self.__running

    def write(self, data: str) -> None:
        logger.error(
            "",
            exc_info=True,
            extra={"show_time": False, "show_level": False, "show_path": False},
        )

    def handle_interrupt(self, *args):
        if self.__code_future:
            self.repl_future_interrupted = True
            self.__code_future.set_exception(KeyboardInterrupt())

            return

        # turning this bug into a "feature" for now
        if self.sigint_pressed:
            return
        else:
            self.sigint_pressed = True
            if self.input_task:
                self.input_task.cancel()

            super().write(f"\n{self.INTERRUPT_MSG}\n")
            self.resetbuffer()
            self.__more = 0

    def get_prompt(self) -> str:
        if not hasattr(sys, "ps1"):
            sys.ps1 = ">>> "

        if not hasattr(sys, "ps2"):
            sys.ps2 = "... "

        return sys.ps2 if self.__more else sys.ps1  # type: ignore

    def interact(self, banner=None, exitmsg=None):
        if banner:
            logger.info(f"{banner}")

        from rich.pretty import install

        install()

        self.__more = 0
        self.__running = True
        _original_handler = signal.getsignal(signal.SIGINT)
        self.loop.call_soon_threadsafe(
            partial(signal.signal, signal.SIGINT, self.handle_interrupt)
        )
        while self.__running:
            try:
                try:
                    line = self.raw_input(self.get_prompt())  #  type: ignore
                except EOFError:
                    super().write("\n")
                    break
                except asyncio.CancelledError:
                    continue
                else:
                    self.__more = self.push(line)
            except KeyboardInterrupt:
                self.handle_interrupt()
            else:
                self.sigint_pressed = False
        self.loop.call_soon_threadsafe(
            partial(signal.signal, signal.SIGINT, _original_handler)
        )
        if exitmsg != None and exitmsg != "":
            super().write(f"{exitmsg}\n")

        self.loop.create_task(self.bot.close())

    def stop(self):
        self.__running = False
        if self.input_task:
            self.input_task.cancel()

    def raw_input(self, prompt: str = "") -> Optional[str]:
        try:
            t = asyncio.ensure_future(
                self.loop.run_in_executor(None, partial(input, prompt))
            )
        except RuntimeError:
            return None

        self.input_task = t
        while not t.done():
            pass

        self.input_task = None
        return t.result()

    def push(self, line: Optional[str]):
        if not isinstance(line, str):
            return False

        return super().push(line)

    def runcode(self, code):
        self.__code_future = concurrent.futures.Future()
        future = self.__code_future

        def callback():
            self.repl_future = None
            self.repl_future_interrupted = False

            func = types.FunctionType(code, self.locals)  #  type: ignore
            try:
                coro = func()
            except SystemExit:
                raise
            except KeyboardInterrupt as ex:
                self.repl_future_interrupted = True
                future.set_exception(ex)
                return
            except BaseException as ex:
                future.set_exception(ex)
                return

            if not inspect.iscoroutine(coro):
                future.set_result(coro)
                return

            try:
                self.repl_future = self.loop.create_task(coro)
                futures._chain_future(self.repl_future, future)  # type: ignore
            except BaseException as exc:
                future.set_exception(exc)

        self.loop.call_soon_threadsafe(callback)

        try:
            return self.__code_future.result()
        except SystemExit:
            raise
        except concurrent.futures.CancelledError:
            pass
        except BaseException:
            if self.repl_future_interrupted:
                # pretend the future was cancelled,
                # so that it doesn't complain about
                # it being finished.
                self.__code_future._state = "CANCELLED"  #  type: ignore
                if self.repl_future:
                    self.repl_future.cancel()
                super().write("\nKeyboardInterrupt\n")
            else:
                self.showtraceback()
        finally:
            self.repl_future = None
            self.__code_future = None


class REPLThread(threading.Thread):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from strapbot import StrapBot

        self.bot: StrapBot = bot

    def run(self):
        try:
            p = self.bot.do_give_prefixes(self.bot, None)[0]
            banner = (
                "Welcome to the StrapBot REPL!\n"
                f'Just like "{p}eval", you can evaluate Python codes from here.\n'
                'You can access the bot with "bot". Have fun!'
            )

            self.bot.console.interact(banner=banner)
        finally:
            warnings.filterwarnings(
                "ignore",
                message=r"^coroutine .* was never awaited$",
                category=RuntimeWarning,
            )

            self.bot.console.loop.call_soon_threadsafe(self.bot.close)


"""
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    repl_locals = {"asyncio": asyncio}
    for key in {
        "__name__",
        "__package__",
        "__loader__",
        "__spec__",
        "__builtins__",
        "__file__",
    }:
        repl_locals[key] = locals()[key]

    console = AsyncIOInteractiveConsole(repl_locals, loop)


    try:
        import readline  # NoQA
    except ImportError:
        pass
    
    async def e():
        exit()

    test = type("bot", (object,), {"loop": loop, "console": console, "close": e})

    repl_thread = REPLThread(test)
    repl_thread.daemon = True
    repl_thread.start()

    while True:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            if console.repl_future and not console.repl_future.done():
                console.repl_future.cancel()
                repl_future_interrupted = True
            continue
        else:
            break
"""
