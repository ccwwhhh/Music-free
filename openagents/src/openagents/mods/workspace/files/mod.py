from openagents.mods.base_mod import BaseMod
from .adapter import WorkspaceFilesAdapter


class WorkspaceFilesMod(BaseMod):
    mod_id = "openagents.mods.workspace.files"

    def __init__(self):
        super().__init__()
        self.adapter_class = WorkspaceFilesAdapter
