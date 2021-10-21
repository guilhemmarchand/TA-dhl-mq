const { Callbacks } = require("jquery");

require([
  "jquery",
  "underscore",
  "splunkjs/mvc",
  "splunkjs/mvc/searchcontrolsview",
  "splunkjs/mvc/searchmanager",
  "splunkjs/mvc/postprocessmanager",
  "splunkjs/mvc/dropdownview",
  "splunkjs/mvc/multidropdownview",
  "splunkjs/mvc/tableview",
  "splunkjs/mvc/textinputview",
  "splunkjs/mvc/singleview",
  "splunkjs/mvc/chartview",
  "splunkjs/mvc/resultslinkview",
  "splunkjs/mvc/simplexml/searcheventhandler",
  "splunkjs/mvc/simplexml/ready!",
  "splunkjs/mvc/simpleform/input/multiselect",
], function (
  $,
  _,
  mvc,
  SearchControlsView,
  SearchManager,
  PostProcessManager,
  DropdownView,
  MultiDropdownView,
  TableView,
  TextInputView,
  SingleView,
  ChartView,
  ResultsLinkView,
  SearchEventHandler
) {
  // TOKENS

  var defaultTokenModel = mvc.Components.getInstance("default", {
    create: true,
  });
  var submittedTokenModel = mvc.Components.getInstance("submitted", {
    create: true,
  });

  // table search
  var searchBatches = new SearchManager(
    {
      id: "searchBatches",
      search:
        "| `get_table_batches` | search $batch_uuid$ $status$ $submitter$ $appname$ $manager$ $queue$ $region$ | `format_table_batches`",
      earliest_time: "-5m",
      latest_time: "now",
    },
    {
      tokens: true,
      tokenNamespace: "submitted",
    }
  );

  // table element
  var tableBatches = new TableView(
    {
      id: "tableBatches",
      drilldown: "row",
      managerid: "searchBatches",
      pageSize: "20",
      wrap: true,
      fields:
        "status_batch, batch_uuid, ctime, mtime, submitter, appname, manager, queue, region, count, last_error",
      el: $("#tableBatches"),
    },
    {
      tokens: true,
      tokenNamespace: "submitted",
    }
  ).render();

  // on table click
  tableBatches.on("click", function (e) {
    e.preventDefault();

    // set tokens
    defaultTokenModel.set("tk_batch_uuid", e.data["row.batch_uuid"]);
    defaultTokenModel.set("tk_status", e.data["row.status"]);
    var tk_batch_uuid = e.data["row.status"];
    var tk_status = e.data["row.status"];

    // dynamically set button states
    if (tk_status == "pending") {
      $("#btn_submit_batch").prop("disabled", false);
      $("#btn_cancel_batch").prop("disabled", false);
    } else if (
      tk_status == "success" ||
      tk_status == "canceled" ||
      tk_status == "permanent_failure"
    ) {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", true);
    }
    // show modal
    $("#modal_manage_batch").modal();
  });

  // END
});
