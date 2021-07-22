require(["splunkjs/mvc/simplexml/ready!"], function () {
  require(["splunkjs/ready!", "splunkjs/mvc"], function (mvc) {
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

    // For each button with the class "custom-sub-nav"
    $(".active-button").each(function () {
      var $btn_group = $(this);

      $btn_group.find("button").on("click", function () {
        var $btn = $(this);
        unsetToken("tk_refresh");
        setToken("tk_refresh", "true");
        setToken("tk_hide_validation", "true");
        unsetToken("form.batch_uuid");
      });
    });
  });
});
