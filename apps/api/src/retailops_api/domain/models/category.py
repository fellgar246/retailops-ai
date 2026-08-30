from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, IdMixin, IdType, TimestampMixin


class Category(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A node in the merchandise hierarchy; a null parent marks a root category."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="parent_not_self"),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    parent: Mapped[Category | None] = relationship(
        back_populates="children", remote_side="Category.id"
    )
    # `passive_deletes="all"` stops the ORM from quietly re-parenting children to
    # NULL when a parent is deleted; the ON DELETE RESTRICT rule decides instead.
    children: Mapped[list[Category]] = relationship(back_populates="parent", passive_deletes="all")

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, code={self.code!r})"
