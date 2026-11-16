import streamlit as st

from frontend import client
from frontend.views.common import safe


def render():
    st.header("Runbook search")
    info = safe(client.get, "/runbooks")
    if info:
        st.caption(f"{len(info['runbooks'])} runbooks · {info['chunks']} searchable sections")

    query = st.text_input("Describe the problem", placeholder="database connection timeout")
    k = st.slider("Results", 1, 8, 3)
    if st.button("Search", type="primary") and query.strip():
        data = safe(client.post, "/runbooks/search", json={"query": query, "k": k})
        if data:
            st.caption(f"Embeddings: {data['embedder']}")
            if not data["results"]:
                st.info("No matching runbook sections.")
            for r in data["results"]:
                with st.container(border=True):
                    st.markdown(f"**{r['rank']}. {r['title']}** · {r['section']}  \n`{r['source']}` · score {r['score']}")
                    st.text(r["content"])
