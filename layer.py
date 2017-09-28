import torch
import torch.nn as nn
from torch.autograd import Variable
from torch import optim

class QRNNLayer(nn.Module):
    def __init__(self, input_size, hidden_size, kernel_size, use_attn=False):
        super(QRNNLayer, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.kernel_size = kernel_size
        self.use_attn = use_attn
        
        # quasi_conv_layer
        self.conv1d = nn.Conv1d(in_channels=input_size, out_channels=3*hidden_size, 
                                kernel_size=kernel_size)
        self.conv_linear = nn.Linear(hidden_size, 3*hidden_size)
        self.rnn_linear = nn.Linear(2*hidden_size, hidden_size)

    def _conv_step(inputs, keep_dim=True, memory=None)
        # inputs: [Batch_size, Depth, Length]
        # memory: [Batch_size, Depth, Length']
        if keep_dim:
            pad = torch.zeros(inputs.size()[:2] + [self.kernel_size-1]) # TODO: fix
            inputs = torch.cat([pad, inputs], dim=2)

        gates = self.conv1d(inputs) # gates: [Batch_size, 3*Depth, Length]
        if memory:
            last_memory = memory.split(split_size=1, dim=2)[-1].squeeze(2)	# last_memory: [Batch_size, Depth]
            gates = gates + \
                    self.conv_linear(last_memory).unsqueeze(-1)			# broadcasting the memory's last state
 
        Z, F, O = gates.split(split_size=self.hidden_size, dim=1)
        return Z.tanh_(), F.sigmoid_(), O.sigmoid_()

    def _rnn_step(z, f, o, c, attn_memory=None):
        # uses 'fo pooling' at each time step
        # z, f, o, c: [Batch_size, Depth, 1]
        # self.memory: [Batch_size, Depth, Length']
        c_ = torch.mul(c, f) + torch.mul(z, 1-f)
        
        if not attn_memory:
            return c_, torch.mul(c_, o)	# return c_t and h_t

        alpha = nn.Softmax(torch.bmm(c_.transpose(1, 2), self.memory).squeeze(1))	# alpha: [Batch_size, Length']
        context = torch.sum(alpha.unsqueeze(1) * self.memory, dim=2)			# context: [Batch_size, Depth]
        h_ = self.rnn_linear(torch.cat([c_, context], dim=1)).unsqueeze(-1)
        h_ = torch.mul(o, h_)
            
        # c_, h_: [Batch_size, Depth, 1]
        return c_, h_

    def forward(self, inputs, init_state=None, memory=None):
        # inputs: [Batch_size, Depth, Length] 
        Z, F, O = self._conv_step(inputs, memory)
        
        # set initial state
        c = init_state if init_state else torch.zeros(inputs.size()[:2]).unsqueeze(-1)
        attn_memory = memory if self.use_attn else None	# set whether to use attn
        c_list, h_list = [], []
        for z, f, o in zip(Z.split(1, 2), F.split(1, 2), O.split(1, 2)):
            c, h = self._rnn_step(z, f, o, c, attn_memory)
            c_list.append(c); h_list.append(h)

        # return concatenated cell and hidden states: [Batch_size, Depth, Length]
        return torch.cat(c_list, dim=2), torch.cat(h_list, dim=2)
