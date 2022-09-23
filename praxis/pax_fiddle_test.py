# coding=utf-8
# Copyright 2022 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for pax_fiddle."""

import dataclasses
from typing import Optional, List
from absl.testing import absltest

import fiddle as fdl
from fiddle import testing
from praxis import pax_fiddle


@dataclasses.dataclass
class Wheel:
  radius: int = 5

  def setup(self):
    return self


@dataclasses.dataclass
class ColoredWheel(Wheel):
  color: str = "black"


@dataclasses.dataclass
class Person:
  name: Optional[str] = None

  def setup(self):
    return self


@dataclasses.dataclass
class Vehicle:
  wheel_tpl: pax_fiddle.Config[Wheel] = pax_fiddle.template_field(Wheel)
  num_wheels: int = 4
  owner: Person = pax_fiddle.sub_field(Person)
  wheels: Optional[List[Wheel]] = None  # Initialized by setup.

  def setup(self):
    assert self.wheels is None
    self.wheels = [
        pax_fiddle.build(self.wheel_tpl).setup() for i in range(self.num_wheels)
    ]
    return self


@dataclasses.dataclass
class Fleet:
  vehicle_tpl: pax_fiddle.Config[Vehicle] = pax_fiddle.template_field(Vehicle)
  num_vehicles: int = 1
  manager: Person = pax_fiddle.sub_field(Person)
  vehicles: Optional[List[Vehicle]] = None  # Initialized by setup.

  def setup(self):
    assert self.vehicles is None
    self.vehicles = [
        pax_fiddle.build(self.vehicle_tpl).setup()
        for i in range(self.num_vehicles)
    ]
    return self


class SubFieldAndTemplateFieldTest(testing.TestCase):

  def test_default_fleet_config(self):
    config = pax_fiddle.Config(Fleet)
    with self.subTest("expected_config"):
      self.assertDagEqual(
          config,
          pax_fiddle.Config(
              Fleet,
              vehicle_tpl=pax_fiddle.Config(
                  Vehicle,
                  wheel_tpl=pax_fiddle.Config(Wheel),
                  owner=pax_fiddle.Config(Person)),
              manager=pax_fiddle.Config(Person)))

    with self.subTest("with_materialized_defaults"):
      fdl.materialize_defaults(config)
      self.assertDagEqual(
          config,
          pax_fiddle.Config(
              Fleet,
              vehicle_tpl=pax_fiddle.Config(
                  Vehicle,
                  wheel_tpl=pax_fiddle.Config(Wheel, radius=5),
                  owner=pax_fiddle.Config(Person, name=None),
                  num_wheels=4,
                  wheels=None),
              num_vehicles=1,
              manager=pax_fiddle.Config(Person, name=None),
              vehicles=None))

  def test_build_default_fleet_config(self):
    config = pax_fiddle.Config(Fleet)
    config.manager.name = "Ben"  # Required arg
    fleet = pax_fiddle.build(config)
    self.assertEqual(
        fleet,
        Fleet(
            vehicle_tpl=pax_fiddle.Config(Vehicle),
            num_vehicles=1,
            manager=Person("Ben")))

  def test_build_custom_fleet_config(self):
    config = pax_fiddle.Config(Fleet)
    config.manager.name = "Ben"
    config.num_vehicles = 3
    config.vehicle_tpl.wheel_tpl.radius *= 2
    config.vehicle_tpl.owner = config.manager
    fleet = pax_fiddle.build(config)
    self.assertEqual(
        fleet,
        Fleet(
            vehicle_tpl=pax_fiddle.Config(
                Vehicle,
                wheel_tpl=pax_fiddle.Config(Wheel, radius=10),
                owner=pax_fiddle.Config(Person, name="Ben")),
            num_vehicles=3,
            manager=Person("Ben")))

  def test_build_and_setup_default_fleet_config(self):
    config = pax_fiddle.Config(Fleet)
    config.manager.name = "Ben"  # Required arg
    config.vehicle_tpl.owner.name = "Joe"  # Required arg
    fleet = pax_fiddle.build(config).setup()
    self.assertEqual(
        fleet,
        Fleet(
            vehicle_tpl=pax_fiddle.Config(
                Vehicle, owner=pax_fiddle.Config(Person, name="Joe")),
            vehicles=[
                Vehicle(
                    wheel_tpl=pax_fiddle.Config(Wheel),
                    wheels=[Wheel(), Wheel(),
                            Wheel(), Wheel()],
                    num_wheels=4,
                    owner=Person("Joe"))
            ],
            num_vehicles=1,
            manager=Person("Ben")))

  def test_build_and_setup_custom_fleet_config(self):
    config = pax_fiddle.Config(Fleet)

    config.manager.name = "Ben"
    config.num_vehicles = 3
    config.vehicle_tpl.wheel_tpl.radius *= 2
    config.vehicle_tpl.owner.name = "Joe"

    with self.subTest("got_expected_fleet"):
      fleet = pax_fiddle.build(config).setup()
      self.assertEqual(
          fleet,
          Fleet(
              vehicle_tpl=pax_fiddle.Config(
                  Vehicle,
                  owner=pax_fiddle.Config(Person, name="Joe"),
                  wheel_tpl=pax_fiddle.Config(Wheel, radius=10)),
              vehicles=3 * [
                  Vehicle(
                      wheel_tpl=pax_fiddle.Config(Wheel, radius=10),
                      wheels=4 * [Wheel(10)],
                      num_wheels=4,
                      owner=Person("Joe"))
              ],
              num_vehicles=3,
              manager=Person("Ben")))

    # Check that no sub-objects are unintentionally shared.
    with self.subTest("no_accidental_sharing"):
      self.assertIsNot(fleet.vehicles[0], fleet.vehicles[1])
      self.assertIsNot(fleet.vehicles[0].owner, fleet.vehicles[1].owner)
      self.assertIsNot(fleet.vehicles[0].wheels[0], fleet.vehicles[0].wheels[1])
      self.assertIsNot(fleet.vehicles[0].wheels[0], fleet.vehicles[1].wheels[0])
      self.assertIsNot(fleet.vehicles[0].wheels[0], fleet.vehicles[1].wheels[1])
      self.assertIsNot(fleet.manager, fleet.vehicles[0].owner)

  def test_shared_vehicle_owners(self):
    config = pax_fiddle.Config(Fleet)

    config.manager.name = "Ben"
    config.num_vehicles = 3
    config.vehicle_tpl.owner = config.manager  # shared config object.

    fleet = pax_fiddle.build(config).setup()
    self.assertEqual(
        fleet,
        Fleet(
            vehicle_tpl=pax_fiddle.Config(
                Vehicle, owner=pax_fiddle.Config(Person, name="Ben")),
            vehicles=3 * [
                Vehicle(
                    wheel_tpl=pax_fiddle.Config(Wheel),
                    wheels=4 * [Wheel()],
                    num_wheels=4,
                    owner=Person("Ben"))
            ],
            num_vehicles=3,
            manager=Person("Ben")))

    # Note: there is no object sharing between fleet.manager and
    # fleet.vehicle[i].owner, or between fleet.vehicle[i].owner and
    # fleet.vehicle[j].owner, despite the fact that they were all constructed
    # from the same Config object (by identity).  This lack of sharing occurs
    # because they were all constructed during different calls to
    # pax_fiddle.build.  This will change when we transition to using factory
    # objects (partials) instead of config objects to store templates.
    self.assertIsNot(fleet.vehicles[0].owner, fleet.vehicles[1].owner)
    self.assertIsNot(fleet.vehicles[0].owner, fleet.vehicles[2].owner)
    self.assertIsNot(fleet.vehicles[1].owner, fleet.vehicles[2].owner)
    self.assertIsNot(fleet.manager, fleet.vehicles[0].owner)

  def test_use_custom_wheel(self):
    config = pax_fiddle.Config(Fleet)
    config.vehicle_tpl.wheel_tpl = pax_fiddle.Config(ColoredWheel, color="red")
    fleet = pax_fiddle.build(config).setup()
    self.assertIsInstance(fleet.vehicles[0].wheels[0], ColoredWheel)
    self.assertEqual(fleet.vehicles[0].wheels[0],
                     ColoredWheel(radius=5, color="red"))

  def test_build_fleet_directly(self):
    fleet = Fleet()
    fleet = fleet.setup()
    self.assertEqual(
        fleet,
        Fleet(
            vehicle_tpl=pax_fiddle.Config(Vehicle),
            num_vehicles=1,
            vehicles=[
                Vehicle(
                    wheel_tpl=pax_fiddle.Config(Wheel),
                    num_wheels=4,
                    wheels=[Wheel(), Wheel(),
                            Wheel(), Wheel()],
                    owner=Person())
            ],
            manager=Person()))

    self.assertEqual(fleet.vehicle_tpl, pax_fiddle.Config(Vehicle))
    self.assertEqual(fleet.vehicles[0].wheel_tpl, pax_fiddle.Config(Wheel))


class PaxConfigTest(testing.TestCase):

  def test_clone(self):
    cfg = pax_fiddle.Config(
        Vehicle, wheel_tpl=pax_fiddle.Config(Wheel), num_wheels=3)
    clone = cfg.clone()
    self.assertEqual(cfg, clone)
    self.assertIsNot(cfg, clone)
    self.assertIsNot(cfg.wheel_tpl, clone.wheel_tpl)

  def test_set(self):
    cfg = pax_fiddle.Config(Vehicle)
    cfg.set(num_wheels=2)
    cfg.wheel_tpl.set(radius=20)
    cfg.owner.set(name="Grug")
    self.assertDagEqual(
        cfg,
        pax_fiddle.Config(
            Vehicle,
            num_wheels=2,
            owner=pax_fiddle.Config(Person, "Grug"),
            wheel_tpl=pax_fiddle.Config(Wheel, radius=20)))


if __name__ == "__main__":
  absltest.main()
