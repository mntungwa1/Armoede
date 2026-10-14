"""Faithful, password-gated reference documents for stakeholder engagement."""
import hashlib
import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'documents/manifest.json').read_text())
DOCUMENTS = {
    'plan': ('Armoede DRM Plan', 'Disaster Risk Reduction and Resilience Implementation Plan · 2025–2030', 'Armoede_DRM_Plan', 153),
    'sops': ('Armoede Draft SOPs', 'Milestone 2 · Draft v0.2 · September 2026', 'Armoede_Draft_SOPs', 32),
}
WORD_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

@st.cache_data(show_spinner=False)
def verified_bytes(relative_path, expected_digest):
    parts = MANIFEST[relative_path].get('parts')
    data = b''.join((ROOT / part).read_bytes() for part in parts) if parts else (ROOT / relative_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError('Document integrity check failed: ' + relative_path)
    return data

def document_bytes(stem, extension):
    path = f'documents/{stem}.{extension}'
    return verified_bytes(path, MANIFEST[path]['sha256'])

def render_document(code):
    title, subtitle, stem, pages = DOCUMENTS[code]
    st.markdown('''<style>
    .st-key-document_plan,.st-key-document_sops {border:2px solid #2474a8;border-radius:12px;padding:1rem;}
    [data-testid="stDownloadButton"] button {min-height:48px;}
    </style>''', unsafe_allow_html=True)
    with st.container(border=True, key=f'document_{code}'):
        st.subheader(title)
        st.caption(subtitle)
        st.write('Read the document while answering the survey, or download the Word document to your device.')
        left, right = st.columns(2)
        with left:
            st.button('Preview document', key=f'preview_{code}', use_container_width=True,
                      on_click=lambda: st.session_state.update({f'show_document_{code}': True}))
        with right:
            st.download_button('Download Word document', document_bytes(stem, 'docx'),
                               file_name=f'{stem}.docx', mime=WORD_MIME,
                               key=f'download_{code}', use_container_width=True, on_click='ignore')
        size = MANIFEST[f'documents/{stem}.docx']['bytes'] / 1024**2
        st.caption(f'{pages} pages · Word download {size:.1f} MB. On a phone, allow time for the document to load.')
        if st.session_state.get(f'show_document_{code}'):
            with st.expander(f'Document preview — {title}', expanded=True):
                st.caption('These are the rendered pages of the supplied Word document, including its tables, maps and diagrams.')
                mode = st.selectbox('Preview height', ['Compact (phone)', 'Standard', 'Large'],
                                    key=f'height_{code}')
                height = {'Compact (phone)':450, 'Standard':720, 'Large':1000}[mode]
                data = document_bytes(stem, 'pdf')
                digest = MANIFEST[f'documents/{stem}.pdf']['sha256']
                st.pdf(data, height=height, key=f'pdf_{code}_{digest}', alt=title)
                st.button('Close preview', key=f'close_{code}',
                          on_click=lambda: st.session_state.update({f'show_document_{code}':False}))
