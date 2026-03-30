import pytest

from airex_core.investigations.k8s_probe import K8sStatusProbe, should_run_k8s_status_probe


def test_should_run_k8s_status_probe_detects_k8s_meta():
    assert should_run_k8s_status_probe({"_platform": "k8s"}) is True
    assert should_run_k8s_status_probe({"namespace": "prod"}) is True
    assert should_run_k8s_status_probe({"deployment_name": "checkout"}) is True
    assert should_run_k8s_status_probe({"host": "web-1"}) is False


@pytest.mark.asyncio
async def test_k8s_status_probe_returns_structured_result():
    probe = K8sStatusProbe()
    result = await probe.investigate(
        {
            "_platform": "k8s",
            "_k8s_namespace": "prod",
            "_k8s_deployment": "checkout",
            "_k8s_pod": "checkout-7b5f6",
            "restart_count": 4,
            "desired_replicas": 3,
            "unavailable_replicas": 1,
        }
    )

    assert result.tool_name == "k8s_status"
    assert result.metrics["namespace"] == "prod"
    assert result.metrics["deployment"] == "checkout"
    assert result.metrics["restart_count"] == 4
    assert "Diagnosis:" in result.raw_output
