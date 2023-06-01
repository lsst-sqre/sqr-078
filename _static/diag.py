import os

from diagrams import Cluster, Diagram, Edge
from diagrams.generic.storage import Storage
from diagrams.k8s.compute import Deployment, Pod
from diagrams.k8s.network import Ingress, Service
from diagrams.onprem.client import User, Client
from diagrams.programming.flowchart import Action, Decision, Display

os.chdir(os.path.dirname(__file__))

edge_attr = {
    "labelloc": "c"
}

graph_attr = {
    "label": "",
    "labelloc": "t",
    "nodesep": "0.2",
    "pad": "0.2",
    "ranksep": "0.75",
    "splines": "spline",
}

node_attr = {
    "fontsize": "12.0",
    "labelloc": "c"
}

with Diagram(
    "Acquire Fileserver",
    show=False,
    filename="acquire-fileserver",
    outformat="svg",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr    
):
    user=User("User", labelloc="b")
    browser=Client("Browser",  labelloc="b")
    with Cluster("Fileserver Controller"):
        ok=Decision("Fileserver OK?")
        complete=Display("Explanatory text")
        ok >> Edge(label="Yes") >> complete
        ok >> Edge(label="No") >> Action("Create Fileserver") >> complete
    user >> Edge(label="Acquire Fileserver") >> browser
    browser >> Edge(label="GET /files")
    complete >> Edge(label="text response") >> browser

with Diagram(
    "Acquire Fileserver Token",
    show=False,
    filename="acquire-token",
    outformat="svg",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr    
):
    user=User("User", labelloc="b")
    browser=Client("Browser", labelloc="b")
    with Cluster("Gafaelfawr"):
        gf = Deployment("Gafaelfawr",  labelloc="b")
    user >> Edge(label="Acquire Fileserver Token") >> browser
    browser >> Edge(label="GET /auth/token") >> gf
    gf >> Edge(label="token") >> browser

with Diagram(
    "File Transfer",
    show=False,
    filename="file-transfer",
    outformat="svg",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr
):
    user=User("User",  labelloc="b")
    webdav=Client("WebDAV",  labelloc="b")
    with Cluster("User Fileserver"):
        ing=Ingress("/files/<user>",  labelloc="b")
        pod=Pod("User Fileserver",  labelloc="b")
        fs_contents = [ ing,
                        pod
                       ]
        ing >> pod
    with Cluster("External Storage"):
        disk=Storage("User Data",  labelloc="b")
    pod - disk
    user >> Edge(label="Manipulate Files") >> webdav
    webdav >> Edge(
        label="Headers: { Authorization: Bearer <token> }" ) >> ing
    pod << Edge(label="file transfer") >> webdav

with Diagram(
    "Delete Fileserver",
    show=False,
    filename="delete-fileserver",
    outformat="svg",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr
):

    with Cluster("User Fileserver"):
        ing=Ingress("/files/<user>",  labelloc="b")
        pod=Pod("User Fileserver",  labelloc="b")
        fs_contents = [ ing,
                        pod
                       ]
        ing >> pod
    with Cluster("External Storage"):
        disk=Storage("User Data",  labelloc="b")
    pod - disk
    pod >> Edge(label="inactivity timeout") >> Action(
        "Delete Fileserver") >> Edge(label="shut down") >> pod




    
