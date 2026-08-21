from prompt.launcher import PromptLauncher


class PromptLauncherService:
    def __init__(self):
        self.launcher = PromptLauncher()

    def generate(
        self,
        target="chatgpt",
        *,
        objective="",
        query="",
        file_name="",
    ):
        return self.launcher.generate(
            target,
            objective=objective,
            query=query,
            file_name=file_name,
        )
