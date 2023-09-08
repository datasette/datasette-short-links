from datasette import hookimpl, Response, Permission, Forbidden
import json
from ulid import ULID

CREATE_LINKS_SQL = """
  CREATE TABLE IF NOT EXISTS datasette_short_links_links(
    id ULID PRIMARY KEY,
    path TEXT,
    querystring TEXT,
    actor TEXT,
    hits INT,
    last_accessed_at DATETIME
  )
"""

LOOKUP_LINK_SQL = "SELECT * FROM datasette_short_links_links WHERE id = :id"

DELETE_LINK_SQL = "DELETE FROM datasette_short_links_links WHERE id = :id"

HIT_LINK_SQL = "UPDATE datasette_short_links_links SET hits = hits + 1, last_accessed_at = datetime('now') WHERE id = :id"

INSERT_LINK = """
  INSERT INTO datasette_short_links_links(id, path, querystring, actor, hits)
  VALUES (:id, :path, :querystring, :actor, 0)
"""

ALL_LINKS_SQL = "SELECT * FROM datasette_short_links_links"


async def initialize_datasette_short_links(datasette) -> str:
    """Initializes the datasette-short-links internal database tables."""
    internal_db = datasette.get_internal_database()
    await internal_db.execute_write(CREATE_LINKS_SQL)

    return id


async def link_new(datasette, path: str, querystring: str, actor) -> str:
    """Creates a new short link, returning the new link ID"""
    internal_db = datasette.get_internal_database()
    base_url = datasette.setting("base_url")

    id = str(ULID()).lower()
    if base_url is not None and path.startswith(base_url):
        path = path[len(base_url) :]

    if path.startswith("-/l/"):
        raise Exception("cannot make a short link of another short link")
    actor_id = None if actor is None else actor.get("id")

    await internal_db.execute_write(
        INSERT_LINK,
        {"id": id, "path": path, "querystring": querystring, "actor": actor_id},
    )

    return id


async def link_lookup(datasette, id: str) -> str:
    """Given a link ID, return the URL path of the redirect target"""
    internal_db = datasette.get_internal_database()
    base_url = datasette.setting("base_url") or "/"

    result = await internal_db.execute(LOOKUP_LINK_SQL, {"id": id})
    row = result.first()
    if row is None:
        return None
    return base_url + row["path"] + row["querystring"]

async def link_hit(datasette, id:str) -> str:
    internal_db = datasette.get_internal_database()
    def update(conn):
        conn.execute(HIT_LINK_SQL, {"id": id})
        conn.commit()
    await internal_db.execute_write_fn(update)

async def link_delete(datasette, id: str):
    """Given a link ID, delete it from the database"""
    internal_db = datasette.get_internal_database()
    await internal_db.execute_write(DELETE_LINK_SQL, {"id": id}, block=True)


async def link_all(datasette) -> str:
    """Return all the registered short links, for the admin panel"""
    base_url = datasette.setting("base_url") or "/"
    internal_db = datasette.get_internal_database()
    rows = await internal_db.execute(ALL_LINKS_SQL)
    links = []
    for row in rows:
        links.append(
            {
                **row,
                "short_url": base_url + f"-/l/{row['id']}",
                "resolved_url": base_url
                + (
                    row["path"]
                    if not row["querystring"]
                    else f"{row['path']}?{row['querystring']}"
                ),
                "created_at": ULID.from_str(row["id"]).milliseconds,
            }
        )

    return links


@hookimpl
async def startup(datasette):
    await initialize_datasette_short_links(datasette)


@hookimpl
def register_permissions(datasette):
    return [
        Permission(
            name="short-links-admin",
            abbr=None,
            description="View the admin page for datasette-short-links.",
            takes_database=False,
            takes_resource=False,
            default=False,
        ),
        Permission(
            name="short-links-create",
            abbr=None,
            description="Ability to create a short link,",
            takes_database=False,
            takes_resource=False,
            default=False,
        ),
    ]


@hookimpl
def permission_allowed(actor, action):
    if action == "short-links-admin" and actor and actor.get("id") == "root":
        return True
    # Any non-none actor can create a short link
    if action == "short-links-create" and actor:
        return True


@hookimpl
def menu_links(datasette, actor):
    async def inner():
        if await datasette.permission_allowed(
            actor, "short-links-admin", default=False
        ):
            return [
                {
                    "href": datasette.urls.path("/-/datasette-short-links/admin"),
                    "label": "short-links Admin Page",
                },
            ]

    return inner


@hookimpl
async def extra_body_script(
    template, database, table, columns, view_name, request, datasette
):
    base_url = datasette.setting("base_url")
    print(request)
    skip_button = request is None or (
        not await datasette.permission_allowed(
            request.actor, "short-links-create", default=False
        )
    )
    return f"""
      window.DATASETTE_SHORT_LINKS_BASE_URL = {json.dumps(base_url)};
      window.DATASETTE_SHORT_LINKS_SKIP_BUTTON = {json.dumps(skip_button)};
    """


@hookimpl
def extra_js_urls(template, database, table, columns, view_name, request, datasette):
    return [datasette.urls.path("/-/static-plugins/datasette-short-links/index.js")]


@hookimpl
def register_routes():
    return [
        (r"^/-/l/(?P<id>.*)$", route_link),
        (r"^/-/datasette-short-links/claim$", route_claim),
        (r"^/-/datasette-short-links/admin$", route_admin),
        (r"^/-/datasette-short-links/delete$", route_delete),
    ]


async def route_claim(scope, receive, datasette, request):
    if not await datasette.permission_allowed(
        request.actor, "short-links-create", default=False
    ):
        raise Forbidden("Permission denied for short-links-create")

    if request.method != "POST":
        return Response.text("", status=405)

    data = json.loads((await request.post_body()).decode("utf8"))
    path = data.get("path")
    querystring = data.get("querystring")

    try:
        id = await link_new(datasette, path, querystring, request.actor)
        return Response.json({"id": id, "url_path": datasette.urls.path(f"/-/l/{id}")})
    except Exception as error:
        return Response.json({"ok": False, "error": str(error)}, status=400)


async def route_delete(scope, receive, datasette, request):
    if not await datasette.permission_allowed(
        request.actor, "short-links-admin", default=False
    ):
        raise Forbidden("Permission denied for short-links-admin")

    if request.method != "DELETE":
        return Response.text("", status=405)

    link_id = request.args.get("link_id")

    await link_delete(datasette, link_id)
    return Response.json({"ok": True})


async def route_link(scope, receive, datasette, request):
    id = request.url_vars["id"]
    link = await link_lookup(datasette, id)

    if link is None:
        return Response.text("not found", status=404)

    await link_hit(datasette, id)

    return Response.redirect(link)


async def route_admin(scope, receive, datasette, request):
    if not await datasette.permission_allowed(
        request.actor, "short-links-admin", default=False
    ):
        raise Forbidden("Permission denied for short-links-admin")

    links = await link_all(datasette)
    return Response.html(
        await datasette.render_template(
            "datasette-short-links-admin.html",
            context={"links": links, "base_url": datasette.setting("base_url")},
        )
    )
