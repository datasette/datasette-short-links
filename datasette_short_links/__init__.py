from datasette import hookimpl, Response, Forbidden
import json
from ulid import ULID

CREATE_LINKS_SQL = """
  CREATE TABLE IF NOT EXISTS datasette_short_links_links(
    id ULID PRIMARY KEY,
    path TEXT,
    querystring TEXT,
    actor TEXT
  )
"""

LOOKUP_LINK_SQL = "SELECT * FROM datasette_short_links_links WHERE id = :id"

INSERT_LINK = """
  INSERT INTO datasette_short_links_links(id, path, querystring, actor)
  VALUES (:id, :path, :querystring, :actor)
"""

ALL_LINKS_SQL = "SELECT * FROM datasette_short_links_links"


async def link_create(datasette) -> str:
    internal_db = datasette.get_internal_database()
    await internal_db.execute_write(CREATE_LINKS_SQL)

    return id


async def link_new(datasette, path: str, querystring: str, actor) -> str:
    internal_db = datasette.get_internal_database()
    base_url = datasette.setting("base_url")

    id = str(ULID()).lower()

    if base_url is not None and path.startswith(base_url):
        path = path[len(base_url):]

    actor_id = None if actor is None else actor.get('id')

    await internal_db.execute_write(
        INSERT_LINK,
        {
            "id": id,
            "path": path,
            "querystring": querystring,
            "actor": actor_id
        },
    )

    return id


async def link_lookup(datasette, id: str) -> str:
    internal_db = datasette.get_internal_database()
    base_url = datasette.setting("base_url") or "/"

    result = await internal_db.execute(LOOKUP_LINK_SQL, {"id": id})
    row = result.first()
    if row is None:
        return None

    return base_url + row["path"] + row["querystring"]


async def link_all(datasette) -> str:
    base_url = datasette.setting("base_url") or "/"
    internal_db = datasette.get_internal_database()
    rows = await internal_db.execute(ALL_LINKS_SQL)
    links = []
    for row in rows:
        links.append({
            **row,
            "url": base_url + (row["path"] if not row["querystring"] else f"{row['path']}?{row['querystring']}"),
            "created_at": ULID.from_str(row["id"]).milliseconds
        })

    return links


# TODO: re-add CSRF to claim route
@hookimpl
def skip_csrf(scope):
    return "datasette-short-links/claim" in scope["path"]


@hookimpl
def register_routes():
    return [
        (r"^/-/l/(?P<id>.*)$", route_link),
        (r"^/-/datasette-short-links/claim$", route_claim),
        (r"^/-/datasette-short-links/admin$", route_admin),
    ]


@hookimpl
def extra_js_urls(template, database, table, columns, view_name, request, datasette):
    return [datasette.urls.path("/-/static-plugins/datasette-short-links/index.js")]


@hookimpl
async def startup(datasette):
    await link_create(datasette)


async def route_claim(scope, receive, datasette, request):
    if request.method != "POST":
        return Response.text("", status=405)

    data = json.loads((await request.post_body()).decode("utf8"))
    path = data.get("path")
    querystring = data.get("querystring")

    id = await link_new(datasette, path, querystring, request.actor)

    return Response.json({"id": id, "url_path": datasette.urls.path(f"/-/l/{id}")})


async def route_link(scope, receive, datasette, request):
    id = request.url_vars["id"]
    link = await link_lookup(datasette, id)

    if link is None:
        return Response.text("not found", status=404)

    return Response.redirect(link)


async def route_admin(scope, receive, datasette, request):
    links = await link_all(datasette)
    return Response.html(
        await datasette.render_template(
            "datasette-short-links-admin.html", context={"links": links}
        )
    )
