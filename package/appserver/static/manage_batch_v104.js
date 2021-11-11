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

  //
  // Notify
  //

  function notify(varCss, varPosition, varHtml, vardelay) {
    require([
      "jquery",
      "/static/app/TA-dhl-mq/notifybar/jquery.notifyBar.js",
    ], function ($) {
      //code here
      jQuery(function () {
        jQuery.notifyBar({
          cssClass: varCss,
          position: varPosition,
          html: varHtml,
          delay: vardelay,
        });
      });
    });
  }

  // preset search filter based on user's application perimeters
  function presetUserFilter() {
    var service = mvc.createService();
    service.currentUser(function (err, user) {
      // set a token containing the user roles
      var tk_user_roles = user.properties().roles;
      setToken("tk_user_roles", tk_user_roles);

      // set the list of applications
      var rolesArray = tk_user_roles.toString().split(",");
      var appArray = [];
      var appArrayHtml = [];
      var appStringSearch = "";
      var appStringHtml = "";
      var role;
      for (role of rolesArray) {
        // for each role the user is member of, attempt to extract the MQ app name and push to the array
        if (/mqsubmission_/i.test(role)) {
          regex_matches = role.match(/mqsubmission_([^\_]+)_\w+/);
          appName = regex_matches[1];
          appArray.push(appName);
          appArrayHtml.push(appName);
        }
      }

      // if null, the user has access to the app but is not a member of an MQ role, likely admin like, set to all
      if (appArray.length === 0) {
        appArray.push("*");
        appArrayHtml.push("All applications (not a member of any MQ group)");
      }

      // dedup the array
      appArrayHtml = [...new Set(appArrayHtml)];

      // set the root search, and the token
      appStringSearch = 'appname="' + appArray.join('" OR appname="') + '"';
      appStringHtml = "[ " + appArrayHtml.join(", ") + " ]";
      appStringHtml = appStringHtml.toUpperCase();
      setToken("tk_user_app_searchstring", appStringSearch);

      // Notify
      notify(
        "info",
        "bottom",
        "We have automatically restricted the content based on your MQ roles membership, for the following application(s): " +
          appStringHtml,
        "10"
      );
    });
  }

  // call it now
  presetUserFilter();

  // prefill modal with required user role
  function fillRequiredUserRole(msg) {
    $("#modal_batch_approver_not_granted")
      .find(".modal-error-message p")
      .text(msg);
  }

  // table search
  var searchBatches = new SearchManager(
    {
      id: "searchBatches",
      search:
        "| `get_table_batches` | search $tk_user_app_searchstring$ $batch_uuid$ $status$ $submitter$ $appname$ $manager$ $queue$ $region$ $validation_required$ | `format_table_batches`",
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
        "status_batch, batch_uuid, ctime, mtime, submitter, appname, manager, queue, region, comment, count, last_error",
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
    defaultTokenModel.set(
      "tk_validation_required",
      e.data["row.validation_required"]
    );
    defaultTokenModel.set("tk_submitter", e.data["row.submitter"]);
    var tk_batch_uuid = e.data["row.batch_uuid"];
    var tk_status = e.data["row.status"];
    var tk_submitter = e.data["row.submitter"];
    var tk_validation_required = e.data["row.validation_required"];
    var tk_user_roles = getToken("tk_user_roles");
    var tk_appname = e.data["row.appname"];

    // RBAC:
    // To allow approving, a user must be member of a role as:
    // mqsubmission_<appName>_approver
    // members of the role mqsubmission_superadmin can approve or manage batches for all applications

    var rolesArray = tk_user_roles.toString().split(",");
    var approveRequiredRole =
      "mqsubmission_" + tk_appname.toLowerCase() + "_approver";
    var approveSuperAdminRole = "mqsubmission_superadmin";
    if (rolesArray.indexOf(approveRequiredRole) > -1) {
      canApprove = true;
    } else if (rolesArray.indexOf(approveSuperAdminRole) > -1) {
      canApprove = true;
    } else {
      canApprove = false;
    }

    // rbac message if permissions are insuffiscients
    var rbac_msg =
      "" +
      approveRequiredRole +
      " is required, you are currently a member of the following roles: " +
      tk_user_roles.toString() +
      ".";

    // Enter dynamic conditions
    if (tk_status == "pending" && tk_validation_required == 1 && canApprove) {
      $("#btn_submit_batch").prop("disabled", false);
      $("#btn_cancel_batch").prop("disabled", false);
      // show modal
      $("#modal_manage_batch").modal();
    } else if (
      tk_status == "pending" &&
      tk_validation_required == 1 &&
      !canApprove
    ) {
      fillRequiredUserRole(rbac_msg);
      $("#modal_batch_approver_not_granted").modal();
    } else if (
      tk_status == "pending" &&
      tk_validation_required == 0 &&
      canApprove
    ) {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", false);
      // show modal
      $("#modal_manage_batch").modal();
    } else if (
      tk_status == "pending" &&
      tk_validation_required == 0 &&
      !canApprove
    ) {
      fillRequiredUserRole(rbac_msg);
      $("#modal_batch_approver_not_granted").modal();
    } else if (tk_status == "success") {
      // show modal
      $("#modal_procedded_successful").modal();
    } else if (tk_status == "canceled") {
      // show modal
      $("#modal_batch_canceled").modal();
    } else if (tk_status == "permanent_failure") {
      // show modal
      $("#modal_batch_permanent_failure").modal();
    } else if (tk_status == "temporary_failure" && canApprove) {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", false);
      // show modal
      $("#modal_manage_batch").modal();
    } else if (tk_status == "temporary_failure" && !canApprove) {
      fillRequiredUserRole(rbac_msg);
      $("#modal_batch_approver_not_granted").modal();
    }
    // something we've missed?
    else {
      $("#btn_submit_batch").prop("disabled", true);
      $("#btn_cancel_batch").prop("disabled", true);
      // show modal
      $("#modal_manage_batch").modal();
    }
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

    // spinner
    $("#cssloader").remove();
    $("body").append(
      '<div id="cssloader" class="loader loader-default is-active" data-text="Loading..."></div>'
    );

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
        $("#cssloader").remove();
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
                    } else if (field === "_raw") {
                      jobResult = value;
                    }
                  }

                  // Identify the operation result
                  if (jobResult.includes("success")) {
                    $("#cssloader").remove();
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
                    $("#cssloader").remove();
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
              $("#cssloader").remove();
              $("#modal_generic_error")
                .find(".modal-error-message p")
                .text(errorStr);
              $("#modal_generic_error").modal();
            },
            error: function (err) {
              done(err);
              $("#cssloader").remove();
              $("#modal_update_collection_failure_flush").modal();
            },
          }
        );
      }
    });
  });

  $("#btn_cancel_batch").click(function () {
    $(this).blur();
    //console.log("Cancel this batch");

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

    // spinner
    $("#cssloader").remove();
    $("body").append(
      '<div id="cssloader" class="loader loader-default is-active" data-text="Loading..."></div>'
    );

    // Define the query
    var searchQuery =
      '| managebatch batch_uuid="' +
      tk_batch_uuid +
      '" action="cancel" comment="' +
      tk_comment +
      '"';
    //console.log(searchQuery);

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
                    } else if (field === "_raw") {
                      jobResult = value;
                    }
                  }

                  // Identify the operation result
                  if (jobResult.includes("success")) {
                    $("#cssloader").remove();
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
                    $("#cssloader").remove();
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
              $("#cssloader").remove();
              $("#modal_generic_error")
                .find(".modal-error-message p")
                .text(errorStr);
              $("#modal_generic_error").modal();
            },
            error: function (err) {
              done(err);
              $("#cssloader").remove();
              $("#modal_update_collection_failure_flush").modal();
            },
          }
        );
      }
    });
  });

  // END
});
