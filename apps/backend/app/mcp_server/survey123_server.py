import json

from mcp.server.fastmcp import FastMCP

from app.core.contracts import Fact
from app.db import SessionLocal
from app.modules.survey123.metrics import METRIC_FUNCTIONS, METRIC_SPECS

mcp_app = FastMCP("survey123")


def _make_tool(metric_fn):
    def tool(params: dict) -> str:
        session = SessionLocal()
        try:
            facts: list[Fact] = metric_fn(params, session)
        finally:
            session.close()
        return json.dumps([f.model_dump(mode="json") for f in facts])

    return tool


for _spec in METRIC_SPECS:
    mcp_app.add_tool(_make_tool(METRIC_FUNCTIONS[_spec.name]), name=_spec.name, description=_spec.description)


if __name__ == "__main__":
    mcp_app.run()
