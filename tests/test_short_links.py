from datasette import hookimpl
from datasette.app import Datasette
from datasette.plugins import pm
import pytest
from ulid import ULID
from datasette_short_links import link_all


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-short-links" in installed_plugins


@pytest.mark.asyncio
async def test_link_basic():
    datasette = Datasette(memory=True)
    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 200
    data = response.json()
    id = ULID.from_str(data["id"])
    assert id is not None
    expected_link = f"/-/l/{str(id).lower()}"
    assert data["url_path"] == expected_link

    # Should only be 1 link in the DB, with no hits
    all_links = await link_all(datasette)
    assert len(all_links) == 1
    assert all_links[0].get("hits") == 0
    assert all_links[0].get("last_accessed_at") == None

    response = await datasette.client.get(expected_link)
    assert response.status_code == 302
    assert response.headers.get("location") == "/_memory.json?sql=select+1;"

    # Now there should be 1 hit
    all_links = await link_all(datasette)
    assert len(all_links) == 1
    assert all_links[0].get("hits") == 1
    assert all_links[0].get("last_accessed_at") is not None

    # try 2 hits!
    response = await datasette.client.get(expected_link)
    assert response.status_code == 302
    all_links = await link_all(datasette)
    assert len(all_links) == 1
    assert all_links[0].get("hits") == 2
    assert all_links[0].get("last_accessed_at") is not None

    response = await datasette.client.delete(
        f"/-/datasette-short-links/delete?link_id={str(id).lower()}",
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
        headers={
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.text == '{"ok": true}'

    response = await datasette.client.get(expected_link)
    assert response.status_code == 404

    # make sure anon cannot claim a URL
    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
    )
    assert response.status_code == 403

    # anon also cannot delete a URL
    response = await datasette.client.delete(
        f"/-/datasette-short-links/delete?link_id={str(id).lower()}",
        headers={
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_link_loop():
    datasette = Datasette(memory=True)
    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url_path"].startswith("/-/l/")

    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": data["url_path"]},
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )

    assert response.status_code == 400
    assert (
        response.text
        == '{"ok": false, "error": "cannot make a short link of another short link"}'
    )


@pytest.mark.asyncio
async def test_link_basic_with_base_url():
    datasette = Datasette(memory=True, settings={"base_url": "/based_url/"})
    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": "_memory.json", "querystring": "?sql=select+1;"},
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 200
    data = response.json()
    id = ULID.from_str(data["id"])
    assert id is not None
    expected_link = f"/based_url/-/l/{str(id).lower()}"
    assert data["url_path"] == expected_link
    print(expected_link)

    # fun fact: datasette.client adds the base_url anyway, so strip it from this
    response = await datasette.client.get(expected_link[len("/based_url/") :])
    assert response.status_code == 302
    assert response.headers.get("location") == "/based_url/_memory.json?sql=select+1;"


@pytest.mark.asyncio
async def test_admin_page():
    # only the root user and jasmine should be able to see the admin page
    datasette = Datasette(
        memory=True, metadata={"permissions": {"short-links-admin": {"id": "jasmine"}}}
    )
    response = await datasette.client.get(
        "/-/datasette-short-links/admin",
    )
    assert response.status_code == 403

    response = await datasette.client.get(
        "/-/datasette-short-links/admin",
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 200

    response = await datasette.client.get(
        "/-/datasette-short-links/admin",
        cookies={"ds_actor": datasette.sign({"a": {"id": "random-guy"}}, "actor")},
    )
    assert response.status_code == 403

    response = await datasette.client.get(
        "/-/datasette-short-links/admin",
        cookies={"ds_actor": datasette.sign({"a": {"id": "jasmine"}}, "actor")},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_actor_names():
    class ActorsFromIdsPlugin:
        __name__ = "ActorsFromIdsPlugin"

        @hookimpl
        def actors_from_ids(self, datasette, actor_ids):
            return {
                "1": {"id": "1", "name": "Alex"},
                "2": {"id": "2"},
                "3": None,
            }

    try:
        pm.register(ActorsFromIdsPlugin(), name="ActorsFromIdsPlugin")
        datasette = Datasette(memory=True)
        actors2 = await datasette.actors_from_ids(["1", "2", "3"])
        print(actors2)
        assert actors2 == {
            "1": {"id": "1", "name": "Alex"},
            "2": {"id": "2"},
            "3": None,
        }

        await datasette.client.post(
            "/-/datasette-short-links/claim",
            json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
            cookies={"ds_actor": datasette.sign({"a": {"id": "1"}}, "actor")},
        )
        await datasette.client.post(
            "/-/datasette-short-links/claim",
            json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
            cookies={"ds_actor": datasette.sign({"a": {"id": "2"}}, "actor")},
        )
        await datasette.client.post(
            "/-/datasette-short-links/claim",
            json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
            cookies={"ds_actor": datasette.sign({"a": {"id": "3"}}, "actor")},
        )

        all_links = await link_all(datasette)
        assert len(all_links) == 3

        assert all_links[0].get("actor") == "1"
        assert all_links[0].get("actor_name") == "Alex"

        # fallbacks to id when no name
        assert all_links[1].get("actor") == "2"
        assert all_links[1].get("actor_name") == "2"

        # fallbacks to id when no actor
        assert all_links[2].get("actor") == "3"
        assert all_links[2].get("actor_name") == "3"

    finally:
        pm.unregister(name="ReturnNothingPlugin")


@pytest.mark.asyncio
async def test_link_view_instance():
    # only the root user has view-instance permissions!
    datasette = Datasette(memory=True, metadata={"allow": {"id": "root"}})
    response = await datasette.client.post(
        "/-/datasette-short-links/claim",
        json={"path": "/_memory.json", "querystring": "?sql=select+1;"},
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 200
    expected_link = f"/-/l/{response.json()['id']}"

    # anon users should be forbidden to see the link, in this instance
    response = await datasette.client.get(expected_link)
    assert response.status_code == 403

    # But root should be able to
    response = await datasette.client.get(
        expected_link,
        cookies={"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")},
    )
    assert response.status_code == 302
