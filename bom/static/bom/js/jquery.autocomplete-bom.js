(function ($) {
  "use strict";
  $.fn.autocomplete = function (options) {
    options = options || {};
    return this.each(function () {
      var $input = $(this);
      var data = options.data || {};
      var keys = Object.keys(data);
      var minLength = options.minLength == null ? 1 : options.minLength;
      var debounceMs = options.debounce == null ? 0 : options.debounce;
      var sourceUrl = options.source || null;
      var $list = $('<ul class="bom-autocomplete" role="listbox"></ul>');
      var debounceTimer = null;
      var requestSeq = 0;
      $input.css("position", "relative");
      $input.parent().css("position", "relative");
      $input.after($list);
      $list.hide();

      function close() {
        $list.hide().empty();
      }

      function render(matches) {
        if (options.limit) {
          matches = matches.slice(0, options.limit);
        }
        $list.empty();
        matches.forEach(function (k) {
          var $li = $("<li></li>").text(k);
          $li.on("mousedown", function (e) {
            e.preventDefault();
            if (typeof options.onAutocomplete === "function") {
              options.onAutocomplete(k);
            } else {
              $input.val(k);
            }
            close();
          });
          $list.append($li);
        });
        if (matches.length) {
          $list.show();
        } else {
          close();
        }
      }

      function localMatches(q) {
        var lower = q.toLowerCase();
        return keys.filter(function (k) {
          return k.toLowerCase().indexOf(lower) !== -1;
        });
      }

      function runSuggest(q) {
        if (sourceUrl) {
          var seq = ++requestSeq;
          $.getJSON(sourceUrl, { q: q })
            .done(function (resp) {
              if (seq !== requestSeq) {
                return;
              }
              var matches = (resp && resp.results) || [];
              render(matches);
            })
            .fail(function () {
              if (seq === requestSeq) {
                close();
              }
            });
          return;
        }
        render(localMatches(q));
      }

      $input.on("input", function () {
        var q = String($input.val() || "");
        if (q.length < minLength) {
          requestSeq += 1;
          clearTimeout(debounceTimer);
          close();
          return;
        }
        clearTimeout(debounceTimer);
        if (debounceMs > 0) {
          debounceTimer = setTimeout(function () {
            runSuggest(q);
          }, debounceMs);
        } else {
          runSuggest(q);
        }
      });

      $input.on("blur", function () {
        setTimeout(close, 150);
      });
    });
  };
})(jQuery);
