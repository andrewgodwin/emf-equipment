import os
import time
from django.shortcuts import render, redirect
from django import forms
from django.singlefile import SingleFileApp
from grist_api import GristDocAPI

app = SingleFileApp()

# Supply these two env vars plus GRIST_API_KEY
grist_document = os.environ.get("GRIST_DOCUMENT", "")
grist_server = os.environ.get("GRIST_SERVER", "https://grist.orga.emfcamp.org")
api = GristDocAPI(grist_document, server=grist_server)


@app.path("")
def index(request):
    return render(request, "index.html")


class CheckoutForm(forms.Form):
    location = forms.CharField(max_length=200)


@app.path("<int:tool_id>/")
def tool(request, tool_id):
    tool_records = api.fetch_table("Equipment", {"id": tool_id})
    if not tool_records:
        return render(request, "error.html", {"error": "No tool found with that ID"})
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            api.update_records(
                "Equipment",
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


if __name__ == "__main__":
    app.main()
