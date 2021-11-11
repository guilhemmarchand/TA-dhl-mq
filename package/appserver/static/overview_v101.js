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

  // END
});
