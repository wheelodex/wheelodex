# Needed until <https://github.com/pallets-eco/flask-sqlalchemy/pull/1269> is
# merged

from __future__ import annotations
from collections.abc import Iterator
from flask import abort, request
import sqlalchemy as sa
from sqlalchemy.orm import lazyload
from .models import db


def paginate_rows(select: sa.Select, per_page: int) -> RowPagination:
    return RowPagination(select=select, per_page=per_page)


class RowPagination:
    def __init__(self, select: sa.Select, per_page: int) -> None:
        try:
            self.page = int(request.args.get("page", 1))
        except (TypeError, ValueError):
            abort(404)
        if self.page < 1:
            abort(404)
        self.per_page = per_page
        query_offset = (self.page - 1) * self.per_page
        select = select.limit(self.per_page).offset(query_offset)
        self.items = db.session.execute(select).all()
        if not self.items and self.page != 1:
            abort(404)
        sub = select.options(lazyload("*")).order_by(None).subquery()
        self.total: int = db.session.execute(
            sa.select(sa.func.count()).select_from(sub)
        ).scalar()

    def __iter__(self) -> Iterator[sa.Row]:
        return iter(self.items)

    def iter_pages(self) -> Iterator[int | None]:
        left_edge = 2
        left_current = 2
        right_current = 4
        right_edge = 2
        pages = (self.total + self.per_page - 1) // self.per_page
        pages_end = pages + 1
        if pages_end == 1:
            return
        left_end = min(1 + left_edge, pages_end)
        yield from range(1, left_end)
        if left_end == pages_end:
            return
        mid_start = max(left_end, self.page - left_current)
        mid_end = min(self.page + right_current + 1, pages_end)
        if mid_start - left_end > 0:
            yield None
        yield from range(mid_start, mid_end)
        if mid_end == pages_end:
            return
        right_start = max(mid_end, pages_end - right_edge)
        if right_start - mid_end > 0:
            yield None
        yield from range(right_start, pages_end)
