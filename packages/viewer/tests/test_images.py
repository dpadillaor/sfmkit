"""The photos: found by name in a dataset, served as they are."""

import os

import pytest
from fastapi.testclient import TestClient

from sfmview.adapters.images_fs import FsImageStore
from sfmview.adapters.runs_fs import FsRunStore
from sfmview.api import create_app
from sfmview.domain import ImageNotFound
from synthetic import make_run


@pytest.fixture
def data(tmp_path):
    """A projects root with one project in it, and tmp_path outside it."""
    scene = tmp_path / "projects" / "city" / "data" / "scene"
    scene.mkdir(parents=True)
    (scene / "Img02.jpg").write_bytes(b"jpeg of Img02")
    (scene / "Img13.png").write_bytes(b"png of Img13")
    return tmp_path / "projects"


def test_a_photo_is_found_by_its_name_without_extension(data):
    store = FsImageStore(data)
    assert store.image_file("city", "Img02").read_bytes() == b"jpeg of Img02"
    assert store.image_file("city", "Img13").suffix == ".png"


@pytest.mark.parametrize(("dataset", "name"), [
    ("city", "Img99"), ("town", "Img02"), ("..", "Img02"), ("city", "../scene/Img02"),
    ("city", ".hidden"), ("city", ""),
])
def test_what_is_not_a_photo_there_is_not_found(data, dataset, name):
    with pytest.raises(ImageNotFound):
        FsImageStore(data).image_file(dataset, name)


def test_two_files_that_could_both_be_it_are_not_guessed_between(data):
    (data / "city" / "data" / "scene" / "Img02.png").write_bytes(b"another")
    with pytest.raises(ImageNotFound):
        FsImageStore(data).image_file("city", "Img02")


def test_a_symlink_out_of_the_root_is_not_followed(data, tmp_path):
    (tmp_path / "secret.jpg").write_bytes(b"secret")
    os.symlink(tmp_path / "secret.jpg", data / "city" / "data" / "scene" / "Img50.jpg")
    with pytest.raises(ImageNotFound):
        FsImageStore(data).image_file("city", "Img50")


def test_the_api_serves_photos_and_scenes_say_where(data, tmp_path):
    make_run(data, "city", "full")
    client = TestClient(create_app(FsRunStore(data), None, FsImageStore(data)))
    scene = client.get("/api/runs/city/full/scene").json()
    assert scene["images"] == "/api/datasets/city/images"  # the run's config names its dataset
    photo = client.get(f"{scene['images']}/Img02")
    assert photo.status_code == 200 and photo.content == b"jpeg of Img02"
    assert "max-age" in photo.headers["cache-control"]
    assert client.get(f"{scene['images']}/Img99").status_code == 404


def test_a_server_without_photos_says_not_found(tmp_path):
    make_run(tmp_path / "runs", "city", "full")
    client = TestClient(create_app(FsRunStore(tmp_path / "runs")))
    assert client.get("/api/datasets/city/images/Img02").status_code == 404
