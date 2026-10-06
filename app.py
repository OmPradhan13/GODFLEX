import streamlit as st

from main import GODFLEX


st.set_page_config(
    page_title="GODFLEX",
    page_icon="G",
    layout="centered",
)


def get_godflex():
    if "godflex" not in st.session_state:
        st.session_state.godflex = GODFLEX()
    return st.session_state.godflex


def main():
    st.title("GODFLEX")
    st.caption("AI Agent System")

    godflex = get_godflex()

    for message in godflex.conversation:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Message GODFLEX")

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)

        try:
            response = godflex.chat(prompt)
            with st.chat_message("assistant"):
                st.write(response)
        except Exception as error:
            st.error(f"GODFLEX error: {error}")


if __name__ == "__main__":
    main()
