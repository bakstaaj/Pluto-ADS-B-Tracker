#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "airband-pagination-v7"

if marker in s:
    print("Airband pagination v7 is already installed.")
    raise SystemExit(0)

if '<script id="airband-controller-v3">' not in s:
    raise SystemExit(
        "Could not find the clean Airband v3 controller. "
        "Run tools/repair_airband_ui_v3.py first."
    )

if '<section id="airband-panel-v3">' not in s:
    raise SystemExit("Could not find the Airband v3 panel.")

# ---------------------------------------------------------------------------
# Add pagination controls beneath the frequency table.
# ---------------------------------------------------------------------------

selected_anchor = '            <div id="airband-v3-selected">Select a frequency.</div>'

paging_html = r'''            <div id="airband-v3-pagination">
              <button type="button" id="airband-v3-prev">Previous</button>
              <span id="airband-v3-page-info">Page 1 of 1</span>
              <button type="button" id="airband-v3-next">Next</button>
            </div>

'''

if selected_anchor not in s:
    raise SystemExit("Could not find Airband selected-frequency insertion point.")

s = s.replace(selected_anchor, paging_html + selected_anchor, 1)

# ---------------------------------------------------------------------------
# Add compact pagination styling.
# ---------------------------------------------------------------------------

css = r'''
/* airband-pagination-v7 */
#airband-v3-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
  margin-top: 8px;
}
#airband-v3-pagination button {
  padding: 4px 9px;
  border: 1px solid #465058;
  border-radius: 4px;
  background: #262e34;
  color: #eee;
  cursor: pointer;
  font-size: 11px;
}
#airband-v3-pagination button:disabled {
  color: #707880;
  cursor: default;
}
#airband-v3-page-info {
  color: #9da6ad;
  font-size: 11px;
  text-align: center;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style>.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Add paging state.
# ---------------------------------------------------------------------------

old_state = """    lastReceiverKey: ''
  };"""

new_state = """    lastReceiverKey: '',
    pageIndex: 0,
    pageSize: 10,
    pagingReceiverKey: ''
  };"""

if old_state not in s:
    raise SystemExit("Could not find the Airband v3 state-object ending.")

s = s.replace(old_state, new_state, 1)

# ---------------------------------------------------------------------------
# Replace the previous truncated display logic with full-file pagination.
# ---------------------------------------------------------------------------

old_rows_setup = """    const rows = element('airband-v3-rows');
    const list = preparedChannels();

    chooseBest(list);
    rows.innerHTML = '';

    const visible = receiver() ? list.slice(0, 30) : list.slice(0, 60);

    visible.forEach(channel => {"""

new_rows_setup = """    const rows = element('airband-v3-rows');
    const list = preparedChannels();
    const currentReceiverKey = receiverKey();

    /*
     * airband-pagination-v7
     *
     * Changing receiver coordinates changes distance ordering, so restart
     * pagination at the closest records.
     */
    if (stateV3.pagingReceiverKey !== currentReceiverKey) {
      stateV3.pageIndex = 0;
      stateV3.pagingReceiverKey = currentReceiverKey;
    }

    chooseBest(list);

    const totalRecords = list.length;
    const pageCount = Math.max(1, Math.ceil(totalRecords / stateV3.pageSize));

    if (stateV3.pageIndex >= pageCount) {
      stateV3.pageIndex = pageCount - 1;
    }

    if (stateV3.pageIndex < 0) {
      stateV3.pageIndex = 0;
    }

    const startIndex = stateV3.pageIndex * stateV3.pageSize;
    const endIndex = Math.min(startIndex + stateV3.pageSize, totalRecords);
    const visible = list.slice(startIndex, endIndex);

    rows.innerHTML = '';

    const pageInfo = element('airband-v3-page-info');
    const previous = element('airband-v3-prev');
    const next = element('airband-v3-next');

    if (totalRecords) {
      pageInfo.textContent =
        `${startIndex + 1}-${endIndex} of ${totalRecords} · Page ${stateV3.pageIndex + 1} of ${pageCount}`;
    } else {
      pageInfo.textContent = 'No frequencies';
    }

    previous.disabled = stateV3.pageIndex === 0;
    next.disabled = stateV3.pageIndex >= pageCount - 1;

    visible.forEach(channel => {"""

if old_rows_setup not in s:
    raise SystemExit(
        "Could not find the previous Airband row display block. "
        "The controller may differ from the expected v3 layout."
    )

s = s.replace(old_rows_setup, new_rows_setup, 1)

# ---------------------------------------------------------------------------
# Add Previous / Next handlers.
# ---------------------------------------------------------------------------

listen_handler_anchor = """    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);

    loadFrequencies();
"""

listen_handler_replacement = """    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);

    element('airband-v3-prev').addEventListener('click', function () {
      if (stateV3.pageIndex > 0) {
        stateV3.pageIndex--;
        renderRows();
      }
    });

    element('airband-v3-next').addEventListener('click', function () {
      const pageCount = Math.max(
        1,
        Math.ceil(preparedChannels().length / stateV3.pageSize)
      );

      if (stateV3.pageIndex < pageCount - 1) {
        stateV3.pageIndex++;
        renderRows();
      }
    });

    loadFrequencies();
"""

if listen_handler_anchor not in s:
    raise SystemExit("Could not find Airband button initialization block.")

s = s.replace(listen_handler_anchor, listen_handler_replacement, 1)

# ---------------------------------------------------------------------------
# When Select Best Nearby is pressed, jump to the page containing it.
# ---------------------------------------------------------------------------

old_best_selection = """      stateV3.selected = stateV3.recommended;
      renderRows();
"""

new_best_selection = """      stateV3.selected = stateV3.recommended;

      const recommendedIndex = list.findIndex(channel =>
        key(channel) === key(stateV3.recommended)
      );

      if (recommendedIndex >= 0) {
        stateV3.pageIndex = Math.floor(
          recommendedIndex / stateV3.pageSize
        );
      }

      renderRows();
"""

if old_best_selection not in s:
    raise SystemExit("Could not find Select Best Nearby selection block.")

s = s.replace(old_best_selection, new_best_selection, 1)

HTML.write_text(s, encoding="utf-8")

print("Installed Airband pagination v7.")
print("Displays 10 frequencies per page across the complete deployed JSON file.")
print("When receiver location is set, records are sorted nearest-first.")
