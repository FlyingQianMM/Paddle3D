# Copyright (c) 2022 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
import contextlib
import os
from typing import List, Optional

import paddle
import paddle.nn as nn


class BaseDetectionModel(abc.ABC, nn.Layer):
    def __init__(self, box_with_velocity: bool = False):
        super().__init__()
        self.box_with_velocity = box_with_velocity
        self.in_export_mode = False

    @property
    def input_spec(self) -> paddle.static.InputSpec:
        """Input Tensor specifier when exporting the model."""
        data = {
            _input['name']: paddle.static.InputSpec(**_input)
            for _input in self.inputs
        }

        return [data]

    @abc.abstractproperty
    def inputs(self) -> List[dict]:
        """Model input description. This attribute will be used to construct input_spec."""

    @property
    def outputs(self) -> List[dict]:
        """Model output description."""

        boxdim = 7 if not self.box_with_velocity else 9
        box3ds = {'name': 'box3d', 'dtype': 'float32', 'shape': [-1, boxdim]}
        labels = {'name': 'label', 'dtype': 'int32', 'shape': [-1]}
        confidences = {'name': 'confidence', 'dtype': 'float32', 'shape': [-1]}
        return [box3ds, labels, confidences]

    def forward(self, samples):
        if self.in_export_mode:
            return self.export_forward(samples)
        elif self.training:
            return self.train_forward(samples)

        return self.test_forward(samples)

    @abc.abstractproperty
    def sensor(self) -> str:
        """The sensor type used in the model sample, usually camera or lidar."""

    def set_export_mode(self, mode: bool = True):
        for sublayer in self.sublayers(include_self=True):
            sublayer.in_export_mode = mode

    @abc.abstractmethod
    def test_forward(self):
        """Test forward function."""

    @abc.abstractmethod
    def train_forward(self):
        """Training forward function."""

    @abc.abstractmethod
    def export_forward(self):
        """Export forward function."""

    @contextlib.contextmanager
    def exporting(self):
        self.set_export_mode(True)
        yield
        self.set_export_mode(False)

    @property
    def save_name(self):
        return self.__class__.__name__.lower()

    def export(self, save_dir: str, name: Optional[str] = None):
        name = name or self.save_name
        with self.exporting():
            paddle.jit.to_static(self, input_spec=self.input_spec)
            paddle.jit.save(
                self,
                os.path.join(save_dir, name),
                input_spec=[self.input_spec])
