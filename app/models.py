from sqlmodel import SQLModel, Field, create_engine, Session, select

engine = create_engine("sqlite:///intel_graph.db")

class Node(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    kind: str
    x: int | None = None
    y: int | None = None

class Edge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="node.id")
    target_id: int = Field(foreign_key="node.id")
    relation: str

SQLModel.metadata.create_all(engine)

def upsert_node(name: str, kind: str = "GENERIC") -> int:
    with Session(engine) as s:
        node = s.exec(select(Node).where(Node.name == name)).first()
        if not node:
            node = Node(name=name, kind=kind)
            s.add(node); s.commit(); s.refresh(node)
        return node.id

def add_edge(src_name: str, tgt_name: str, relation="mentions"):
    src_id = upsert_node(src_name)
    tgt_id = upsert_node(tgt_name)
    with Session(engine) as s:
        s.add(Edge(source_id=src_id, target_id=tgt_id, relation=relation))
        s.commit()
