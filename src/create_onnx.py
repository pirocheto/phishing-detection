import pickle
from pathlib import Path

import dvc.api
from skl2onnx import to_onnx
from skl2onnx.common.data_types import StringTensorType


def pkl2onnx(model):
    onx = to_onnx(
        model,
        initial_types=[("inputs", StringTensorType((None,)))],
        options={"zipmap": False},
    )
    return onx.SerializeToString()


def create_onnx() -> str:  # pragma: no cover
    params = dvc.api.params_show()
    pkl_path = Path(params["model"]["pickle"])
    model = pickle.loads(pkl_path.read_bytes())

    onx = pkl2onnx(model)

    onnx_path = Path(params["model"]["onnx"])
    onnx_path.write_bytes(onx)
    return onnx_path


if __name__ == "__main__":
    create_onnx()
