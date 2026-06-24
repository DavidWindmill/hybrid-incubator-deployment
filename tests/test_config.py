from pathlib import Path

from deployment.config import load_spec, topological_order


def test_local_spec_is_valid() -> None:
    path = Path(__file__).parents[1] / "specifications" / "application.local.yaml"
    spec, _ = load_spec(path)
    order = topological_order(spec)
    assert order.index("quantum-detector") < order.index("aggregator")
    assert order.index("aggregator") < order.index("sensor-left")
