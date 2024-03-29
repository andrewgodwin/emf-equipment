from collections import defaultdict
import os
import time
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import render, redirect
from django import forms
from django.views.generic.edit import FormView
from django.singlefile import SingleFileApp
from grist_api import GristDocAPI

app = SingleFileApp()

# Supply these two env vars plus GRIST_API_KEY
grist_document = os.environ["GRIST_DOCUMENT"]
grist_server = os.environ.get("GRIST_SERVER", "https://grist.orga.emfcamp.org")
api = GristDocAPI(grist_document, server=grist_server)
table = "Equipment"


@app.path("")
def index(request):
    """
    Top-level index page - just a nice error message
    """
    return render(request, "index.html")


@app.path("<int:tool_id>/")
class ToolView(FormView):

    template_name = "tool.html"

    class form_class(forms.Form):
        location = forms.CharField(max_length=200)

    def get_object(self):
        tool_records = api.fetch_table(table, {"id": self.kwargs["tool_id"]})
        if not tool_records:
            raise Http404("No matching tool")
        return tool_records[0]

    def form_valid(self, form) -> HttpResponse:
        api.update_records(
            table,
            [
                {
                    "id": self.tool.id,
                    "Status": (
                        "In Use"
                        if self.request.POST["action"] == "checkout"
                        else "Available"
                    ),
                    "Location": form.cleaned_data["location"],
                }
            ],
        )
        return redirect(".")

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.tool = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tool"] = self.tool
        return context


@app.path("metrics/")
def stats(request):
    """
    Prometheus stats endpoint for tracking numbers
    """
    counts = defaultdict(int)
    ts = int(time.time() * 1000)
    for row in api.fetch_table(table):
        counts[row.Status] += 1
    res = [
        "# HELP status_count Count of equipment in a given status",
        "# TYPE status_count gauge",
    ]
    for status, count in counts.items():
        res.append(f'status_count{{status="{status}"}} {count} {ts}')
    return HttpResponse(
        "\n".join(res), headers={"Content-Type": "text/plain; version=0.0.4"}
    )


if __name__ == "__main__":
    app.main()
