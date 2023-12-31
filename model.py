import torch
import torch.nn as nn
import torch.nn.functional as F


class GCNLayer(nn.Module):
    def __init__(self, in_feats, out_feats):
        super().__init__()
        self.in_feats = in_feats
        self.out_feats = out_feats
        self.weight = nn.Parameter(torch.FloatTensor(in_feats, out_feats))
        self.norm = nn.LayerNorm(out_feats)
        nn.init.xavier_uniform_(self.weight.data)

    def forward(self, x, adj):
        x = x.matmul(self.weight)
        x = adj.matmul(x)
        x = self.norm(x)
        x = F.relu(x)
        return x


class GraphModule(nn.Module):
    def __init__(self, num_layers, num_feats):
        super().__init__()
        self.wq = nn.Linear(num_feats, num_feats)
        self.wk = nn.Linear(num_feats, num_feats)

        layers = []
        for i in range(num_layers):
            layers.append(GCNLayer(num_feats, num_feats))
        self.gcn = nn.ModuleList(layers)

    def forward(self, x, get_adj=False):
        qx = self.wq(x)
        kx = self.wk(x)
        dot_mat = qx.matmul(kx.transpose(-1, -2))
        adj = F.normalize(dot_mat.square(), p=1, dim=-1)

        for layer in self.gcn:
            x = layer(x, adj)

        x = x.mean(dim=-2)
        if get_adj is False:
            return x
        else:
            return x, adj


class ClassifierSimple(nn.Module):
    def __init__(self, num_feats, num_hid, num_class):
        super().__init__()
        self.fc1 = nn.Linear(num_feats, num_hid)
        self.fc2 = nn.Linear(num_hid, num_class)
        self.drop = nn.Dropout()

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.drop(x)
        x = self.fc2(x)
        return x


class tokengraph_with_global_part_sharing(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.graph_omega = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(2*num_feats, num_feats, num_class)

    def forward(self, feats, feats_global):
        N, FR, B, NF = feats.shape

        feats = feats.view(N * FR, B, NF)
        x = self.graph(feats)
        x = x.view(N, FR, NF)
        x = self.graph_omega(x)
        y = self.graph_omega(feats_global)
        x = torch.cat([x, y], dim=-1)
        x = self.cls(x)
        return x


class cls_only(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.cls = ClassifierSimple(2*num_feats, num_feats, num_class)
    def forward(self, feats, feats_global):

        x = feats.mean(dim=-2)
        x = x.mean(dim=-2)
        y = feats_global.mean(dim=-2)
        x = torch.cat([x, y], dim=-1)
        x = self.cls(x)
        return x


class tokens_as_extra_Graph_mean(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.graph_omega = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(3*num_feats, num_feats, num_class)

    def forward(self, feats, feats_global):
        N, FR, B, NF = feats.shape

        feats = feats.view(N * FR, B, NF)
        x = self.graph_omega(feats)
        x = x.view(N, FR, NF)
        x = self.graph_omega(x)

        x_tokens = self.graph(feats)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = x_tokens.mean(dim=-2)

        y = self.graph_omega(feats_global)
        x = torch.cat([x, x_tokens, y], dim=-1)
        x = self.cls(x)
        return x


class tokenGraph_and_Graph(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.graph_omega3 = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(num_feats, int(num_feats/2), num_class)

    def forward(self, feats):
        N, FR, B, NF = feats.shape
        feats = feats.view(N * FR, B, NF)
        x_tokens = self.graph(feats)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = self.graph_omega3(x_tokens)
        x = self.cls(x_tokens)

        return x

class tokenGraph_and_Graph_shared(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(num_feats, int(num_feats/2), num_class)

    def forward(self, feats):
        N, FR, B, NF = feats.shape
        feats = feats.view(N * FR, B, NF)
        x_tokens = self.graph(feats)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = self.graph(x_tokens)
        x = self.cls(x_tokens)

        return x


class tokenGraph_and_mean(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(num_feats, int(num_feats/2), num_class)

    def forward(self, feats):
        N, FR, B, NF = feats.shape
        feats = feats.view(N * FR, B, NF)
        x_tokens = self.graph(feats)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = x_tokens.mean(dim=-2)
        x = self.cls(x_tokens)

        return x


class Graph_and_tokenGraph(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.graph_omega3 = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(num_feats, int(num_feats/2), num_class)

    def forward(self, feats):
        N, FR, B, NF = feats.shape
        feats = feats.view(N * FR, B, NF)
        x_tokens = self.graph_omega3(feats)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = self.graph(x_tokens)
        x = self.cls(x_tokens)

        return x


class mean_and_tokenGraph(nn.Module):
    def __init__(self, gcn_layers, num_feats, num_class):
        super().__init__()
        self.graph = GraphModule(gcn_layers, num_feats)
        self.cls = ClassifierSimple(num_feats, int(num_feats/2), num_class)

    def forward(self, feats):
        N, FR, B, NF = feats.shape
        feats = feats.view(N * FR, B, NF)
        x_tokens = feats.mean(dim=-2)
        x_tokens = x_tokens.view(N, FR, NF)
        x_tokens = self.graph(x_tokens)
        x = self.cls(x_tokens)

        return x