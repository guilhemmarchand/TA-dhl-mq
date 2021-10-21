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

  function setToken(name, value) {
    defaultTokenModel.set(name, value);
    submittedTokenModel.set(name, value);
  }

  function getToken(name) {
    var ret = null;
    if (defaultTokenModel.get(name) != undefined) {
      ret = defaultTokenModel.get(name);
    } else if (submittedTokenModel.get(name) != undefined) {
      ret = submittedTokenModel.get(name);
    }
    return ret;
  }

  function unsetToken(name) {
    defaultTokenModel.unset(name);
    submittedTokenModel.unset(name);
  }

  // table search
  var searchBatches = new SearchManager(
    {
      id: "searchBatches",
      search:
        "| `get_table_batches` | search $batch_uuid$ $status$ $submitter$ $appname$ $manager$ $queue$ $region$ $validation_required$ | `format_table_batches`",
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
    defaultTokenModel.set("tk_submitter", e.data["row.submitter"]);
    var tk_batch_uuid = e.data["row.batch_uuid"];
    var tk_status = e.data["row.status"];
    var tk_submitter = e.data["row.submitter"];

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
    } else if (tk_status == "temporary_failure") {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", false);
    } else {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", true);
    }

    // show modal
    $("#modal_manage_batch").modal();
  });

  //
  // Handle html textarea
  //

  $(".custom-textarea").each(function () {
    var $text_group = $(this);
    $text_group.find("textarea").on("click", function () {
      var $text = $(this);
      if (this.value == this.defaultValue) this.value = "";
      $(this).blur(function () {
        if (this.value == "") this.value = this.defaultValue;
      });
    });
  });

  // validate the batch
  $("#btn_submit_batch").click(function () {
    $(this).blur();
    //console.log("Submit this batch");

    // Get update note
    var tk_comment = document.getElementById("input_comment").value;

    // get tokens
    var tk_batch_uuid = defaultTokenModel.get("tk_batch_uuid");
    var tk_status = defaultTokenModel.get("tk_status");
    var tk_submitter = defaultTokenModel.get("tk_submitter");

    // Create the service
    var service = mvc.createService({
      owner: "nobody",
    });

    // Define the query
    var searchQuery =
      '| managebatch batch_uuid="' +
      tk_batch_uuid +
      '" action="submit" comment="' +
      tk_comment +
      '"';

    // Set the search parameters--specify a time range
    var searchParams = {
      earliest_time: "-5m",
      latest_time: "now",
    };

    // Run the search
    service.search(searchQuery, searchParams, function (err, job) {
      // Shall the search fail before we can get properties
      if (job == null) {
        let errorStr = "Unknown Error!";
        if (
          err &&
          err.data &&
          err.data.messages &&
          err.data.messages[0]["text"]
        ) {
          errorStr = err.data.messages[0]["text"];
        } else if (err && err.data && err.data.messages) {
          errorStr = JSON.stringify(err.data.messages);
        }
        // show error modal
        $("#modal_generic_error").find(".modal-error-message p").text(errorStr);
        $("#modal_generic_error").modal();
      } else {
        // Poll the status of the search job
        job.track(
          {
            period: 200,
          },
          {
            done: function (job) {
              // Get the results
              job.results({}, function (err, results, job) {
                var fields = results.fields;
                var rows = results.rows;
                var jobResult;
                for (var i = 0; i < rows.length; i++) {
                  var values = rows[i];
                  for (var j = 0; j < values.length; j++) {
                    var field = fields[j];
                    var value = values[j];
                    // get the action
                    if (field === "action") {
                      jobResult = value;
                    }
                  }

                  // Identify the operation result
                  if (jobResult.includes("success")) {
                    $("#modal_generic_success").modal();
                    // refresh relevant searches
                    searchBatches.startSearch();
                    unsetToken("tk_showall");
                    unsetToken("form.status");
                    unsetToken("form.validation_required");
                    setToken("tk_showall", "*");
                    setToken("form.status", "*");
                    setToken("form.validation_required", "*");
                  } else {
                    $("#modal_generic_error")
                      .find(".modal-error-message p")
                      .text(value);
                    $("#modal_generic_error").modal();
                  }
                }
              });
            },
            failed: function (properties) {
              let errorStr = "Unknown Error!";
              if (
                properties &&
                properties._properties &&
                properties._properties.messages &&
                properties._properties.messages[0]["text"]
              ) {
                errorStr = properties._properties.messages[0]["text"];
              } else if (
                properties &&
                properties._properties &&
                properties._properties.messages
              ) {
                errorStr = JSON.stringify(properties._properties.messages);
              }
              $("#modal_generic_error")
                .find(".modal-error-message p")
                .text(errorStr);
              $("#modal_generic_error").modal();
            },
            error: function (err) {
              done(err);
              $("#modal_update_collection_failure_flush").modal();
            },
          }
        );
      }
    });
  });

  $("#btn_cancel_batch").click(function () {
    $(this).blur();
    console.log("Cancel this batch");

    // Get update note
    var tk_comment = document.getElementById("input_comment").value;

    // get tokens
    var tk_batch_uuid = defaultTokenModel.get("tk_batch_uuid");
    var tk_status = defaultTokenModel.get("tk_status");
    var tk_submitter = defaultTokenModel.get("tk_submitter");

    // Create the service
    var service = mvc.createService({
      owner: "nobody",
    });

    // Define the query
    var searchQuery =
      '| managebatch batch_uuid="' +
      tk_batch_uuid +
      '" action="cancel" comment="' +
      tk_comment +
      '"';
    console.log(searchQuery);

    // Set the search parameters--specify a time range
    var searchParams = {
      earliest_time: "-5m",
      latest_time: "now",
    };

    // Run the search
    service.search(searchQuery, searchParams, function (err, job) {
      // Shall the search fail before we can get properties
      if (job == null) {
        let errorStr = "Unknown Error!";
        if (
          err &&
          err.data &&
          err.data.messages &&
          err.data.messages[0]["text"]
        ) {
          errorStr = err.data.messages[0]["text"];
        } else if (err && err.data && err.data.messages) {
          errorStr = JSON.stringify(err.data.messages);
        }
        // show error modal
        $("#modal_generic_error").find(".modal-error-message p").text(errorStr);
        $("#modal_generic_error").modal();
      } else {
        // Poll the status of the search job
        job.track(
          {
            period: 200,
          },
          {
            done: function (job) {
              // Get the results
              job.results({}, function (err, results, job) {
                var fields = results.fields;
                var rows = results.rows;
                var jobResult;
                for (var i = 0; i < rows.length; i++) {
                  var values = rows[i];
                  for (var j = 0; j < values.length; j++) {
                    var field = fields[j];
                    var value = values[j];
                    // get the action
                    if (field === "action") {
                      jobResult = value;
                    }
                  }

                  // Identify the operation result
                  if (jobResult.includes("success")) {
                    $("#modal_generic_success").modal();
                    // refresh relevant searches
                    searchBatches.startSearch();
                    unsetToken("tk_showall");
                    unsetToken("form.status");
                    unsetToken("form.validation_required");
                    setToken("tk_showall", "*");
                    setToken("form.status", "*");
                    setToken("form.validation_required", "*");
                  } else {
                    $("#modal_generic_error")
                      .find(".modal-error-message p")
                      .text(value);
                    $("#modal_generic_error").modal();
                  }
                }
              });
            },
            failed: function (properties) {
              let errorStr = "Unknown Error!";
              if (
                properties &&
                properties._properties &&
                properties._properties.messages &&
                properties._properties.messages[0]["text"]
              ) {
                errorStr = properties._properties.messages[0]["text"];
              } else if (
                properties &&
                properties._properties &&
                properties._properties.messages
              ) {
                errorStr = JSON.stringify(properties._properties.messages);
              }
              $("#modal_generic_error")
                .find(".modal-error-message p")
                .text(errorStr);
              $("#modal_generic_error").modal();
            },
            error: function (err) {
              done(err);
              $("#modal_update_collection_failure_flush").modal();
            },
          }
        );
      }
    });
  });

  // END
});
