import os
import time
from collections import defaultdict
from urllib.parse import quote_plus

from django import forms
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.singlefile import SingleFileApp
from django.views.generic.edit import FormView
from grist_api import GristDocAPI

app = SingleFileApp(ssl_header="HTTP_X_FORWARDED_PROTO")

# Supply these two env vars plus GRIST_API_KEY
grist_document = os.environ["GRIST_DOCUMENT"]
grist_server = os.environ.get("GRIST_SERVER", "https://grist.orga.emfcamp.org")
api = GristDocAPI(grist_document, server=grist_server)
equipment_table = "Equipment"
deliveries_table = "Deliveries"


def api_sql_select(table_name, where):
    # Construct the SQL query
    sql = f"SELECT * FROM {table_name} WHERE {where}"
    records = api.call(f"sql?q={quote_plus(sql)}")["records"]
    return [record["fields"] for record in records]


@app.path("")
def index(request):
    """
    Top-level index page - just a nice error message
    """
    return render(request, "index.html")


@app.path("t/<int:tool_id>/")
class ToolView(FormView):
    """
    Allows tool checkin and checkout
    """

    template_name = "tool.html"

    class form_class(forms.Form):
        location = forms.CharField(max_length=200)

    def get_object(self):
        tool_records = api.fetch_table(equipment_table, {"id": self.kwargs["tool_id"]})
        if not tool_records:
            raise Http404("No matching tool")
        return tool_records[0]

    def form_valid(self, form) -> HttpResponse:
        api.update_records(
            equipment_table,
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


@app.path("d/")
@app.path("d/<int:delivery_id>/")
def delivery(request, delivery_id=None):
    """
    Allows viewing a delivery by tracking number and doing basic actions
    """
    # Look up delivery by tracking number if provided
    tracking = request.GET.get("tracking")
    if tracking:
        # Let's try and avoid SQL injection shall we
        tracking = tracking.lower()
        assert all(c in "abcdefghijklmnopqrstuvwyxz0123456789" for c in tracking)
        deliveries = api_sql_select(
            deliveries_table, f"LOWER(Tracking_Number) = '{tracking}'"
        )
        if not deliveries:
            return render(
                request, "delivery.html", {"error": "Tracking number not found."}
            )
        return redirect(f"/d/{deliveries[0]['id']}/")
    # See if we need to do an action
    if delivery_id and request.method == "POST":
        if request.POST["status"] in ["arrived", "dispatched"]:
            api.update_records(
                deliveries_table,
                [
                    {
                        "id": delivery_id,
                        "Status": request.POST["status"].title(),
                        "Location": request.POST["location"],
                    }
                ],
            )
        elif request.POST["status"] == "collected":
            api.update_records(
                deliveries_table,
                [{"id": delivery_id, "Status": "Collected"}],
            )
        return redirect(".")
    # Fetch a delivery if provided
    delivery = None
    if delivery_id:
        try:
            delivery = api.fetch_table(deliveries_table, {"id": delivery_id})[0]
        except IndexError:
            raise Http404("No such delivery")
    return render(request, "delivery.html", {"delivery": delivery})


@app.path("metrics/")
def stats(request):
    """
    Prometheus stats endpoint for tracking numbers
    """
    counts = defaultdict(int)
    ts = int(time.time() * 1000)
    for row in api.fetch_table(equipment_table):
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
