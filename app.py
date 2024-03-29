from collections import defaultdict
import os
import time
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django import forms
from django.singlefile import SingleFileApp
from grist_api import GristDocAPI

app = SingleFileApp()

# Supply these two env vars plus GRIST_API_KEY
grist_document = os.environ["GRIST_DOCUMENT"]
grist_server = os.environ.get("GRIST_SERVER", "https://grist.orga.emfcamp.org")
api = GristDocAPI(grist_document, server=grist_server)

TABLE = "Equipment"

@app.path("")
def index(request):
    return render(request, "index.html")


class CheckoutForm(forms.Form):
    location = forms.CharField(max_length=200)


@app.path("<int:tool_id>/")
def tool(request, tool_id):
    tool_records = api.fetch_table(TABLE, {"id": tool_id})
    if not tool_records:
        return render(request, "error.html", {"error": "No tool found with that ID"})
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            api.update_records(
                TABLE,
                [
                    {
                        "id": tool_id,
                        "Status": (
                            "In Use"
                            if request.POST["action"] == "checkout"
                            else "Available"
                        ),
                        "Location": form.cleaned_data["location"],
                    }
                ],
            )
            return redirect(".")
    else:
        form = CheckoutForm()
    return render(
        request,
        "tool.html",
        {
            "tool": tool_records[0],
            "form": form,
        },
    )


@app.path("metrics")
def stats(request):
    counts = defaultdict(int)
    ts = int(time.time() * 1000)
    for row in api.fetch_table(TABLE):
        counts[row.Status] += 1
    res = [
        "# HELP status_count Count of equipment in a given status",
        "# TYPE status_count gauge",
    ]
    for status, count in counts.items():
        res.append(f'status_count{{status="{status}"}} {count} {ts}')
    return HttpResponse(
        "\n".join(res),
        headers={"Content-Type": "text/plain; version=0.0.4"}
    )


if __name__ == "__main__":
    app.main()
