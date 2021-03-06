from __future__ import print_function

import time
import socket
import subprocess
import argparse
import uuid
import base64
import threading

import tornado.web
# import tornado.websocket
import tornado.ioloop
import tornado.options
import tornado.httpserver
# import tornado.httpclient
import tornado.gen
import tornado.escape

import setting
import tree
import miner
import leader
import database
import msg
import nameservice

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/node", tree.NodeHandler),
                    (r"/leader", leader.LeaderHandler),
                    (r"/available_branches", AvailableBranchesHandler),
                    (r"/get_highest_block", miner.GetHighestBlockHandler),
                    (r"/get_block", miner.GetBlockHandler),
                    (r"/get_node", GetNodeHandler),
                    (r"/disconnect", DisconnectHandler),
                    (r"/broadcast", BroadcastHandler),
                    # (r"/new_tx", NewTxHandler),
                    (r"/dashboard", DashboardHandler),
                    (r"/new_msg", msg.NewMsgHandler),
                    (r"/get_msg", msg.GetMsgHandler),
                    (r"/wait_msg", msg.WaitMsgHandler),
                    (r"/get_chat", msg.GetChatHandler),
                    (r"/regName", nameservice.RegNameHandler),
                    (r"/getName", nameservice.GetNameHandler),
                    (r"/updateName", nameservice.UpdateNameHandler),
                    ]
        settings = {"debug":True}

        tornado.web.Application.__init__(self, handlers, **settings)


class AvailableBranchesHandler(tornado.web.RequestHandler):
    def get(self):
        branches = list(tree.available_branches)

        # parent = tree.NodeConnector.node_parent:
        self.finish({"available_branches": branches,
                     #"parent": parent,
                     "nodeid": tree.current_nodeid})

class GetNodeHandler(tornado.web.RequestHandler):
    def get(self):
        nodeid = self.get_argument("nodeid")
        target_nodeid = nodeid
        score = None
        address = [tree.current_host, tree.current_port]
        # print(tree.current_port, tree.node_neighborhoods)
        for j in [tree.node_neighborhoods, tree.node_parents]:
            for i in j:
                new_score = tree.node_distance(nodeid, i)
                if score is None or new_score < score:
                    score = new_score
                    target_nodeid = i
                    address = j[target_nodeid]
                # print(i, new_score)

        self.finish({"address": address,
                     "nodeid": target_nodeid,
                     "current_nodeid": tree.current_nodeid})

class DisconnectHandler(tornado.web.RequestHandler):
    def get(self):
        if tree.NodeConnector.node_parent:
            # connector.remove_node = False
            tree.NodeConnector.node_parent.close()

        self.finish({})
        tornado.ioloop.IOLoop.instance().stop()

class BroadcastHandler(tornado.web.RequestHandler):
    def get(self):
        test_msg = ["TEST_MSG", tree.current_nodeid, time.time(), uuid.uuid4().hex]

        tree.forward(test_msg)
        self.finish({"test_msg": test_msg})

class NewTxHandler(tornado.web.RequestHandler):
    def post(self):
        tx = tornado.escape.json_decode(self.request.body)

        tree.forward(["NEW_TX", tx, time.time(), uuid.uuid4().hex])
        self.finish({"txid": tx["transaction"]["txid"]})

class DashboardHandler(tornado.web.RequestHandler):
    def get(self):
        branches = list(tree.available_branches)
        branches.sort(key=lambda l:len(l[2]))

        parents = []
        self.write("<br>current_nodeid: %s <br>" % tree.current_nodeid)

        self.write("<br>pk: %s <br>" % base64.b32encode(tree.node_sk.get_verifying_key().to_string()).decode("utf8"))
        # sender = base64.b32encode(sender_vk.to_string()).decode("utf8")
        self.write("<br>node_parent:<br>")
        if tree.NodeConnector.node_parent:
            self.write("%s:%s<br>" %(tree.NodeConnector.node_parent.host, tree.NodeConnector.node_parent.port))

        self.write("<br>node_parents:<br>")
        for nodeid in tree.node_parents:
            host, port = tree.node_parents[nodeid][0]
            self.write("%s %s:%s<br>" %(nodeid, host, port))

        self.write("<br>node_neighborhoods:<br>")
        for nodeid in tree.node_neighborhoods:
            host, port = tree.node_neighborhoods[nodeid]
            self.write("%s %s:%s <a href='http://%s:%s/dashboard'>dashboard</a><br>" %(nodeid, host, port, host, port))

        self.write("<br>LeaderHandler:<br>")
        for node in leader.LeaderHandler.leader_nodes:
            self.write("%s:%s<br>" %(node.from_host, node.from_port))

        self.write("<br>LeaderConnector:<br>")
        for node in leader.LeaderConnector.leader_nodes:
            self.write("%s:%s<br>" %(node.host, node.port))

        self.write("<br>recent longest:<br>")
        for i in reversed(miner.recent_longest):
            self.write("%s %s %s<br>" % (i['height'], i['hash'], i['identity']))

        self.write("<br>nodes_pool:<br>")
        for nodeid in tree.nodes_pool:
            pk = tree.nodes_pool[nodeid]
            self.write("%s: %s<br>" %(nodeid, pk))

        self.write("<br>nodes_in_chain:<br>")
        for nodeid in miner.nodes_in_chain:
            pk = miner.nodes_in_chain[nodeid]
            self.write("%s: %s<br>" %(nodeid, pk))

        self.write("<br>frozen_nodes_in_chain:<br>")
        for nodeid in miner.frozen_nodes_in_chain:
            pk = miner.frozen_nodes_in_chain[nodeid]
            self.write("%s: %s<br>" %(nodeid, pk))

        self.write("<br>available_branches:<br>")
        for branch in branches:
            self.write("%s:%s %s <br>" % branch)

        self.write("<br>frozen chain:<br>")
        for i, h in enumerate(miner.frozen_chain):
            self.write("%s %s<br>" % (i, h))
        self.finish()

def main():
    tree.main()

    # miner.main()
    tornado.ioloop.IOLoop.instance().call_later(1, miner.looping)

    # leader.main()
    tornado.ioloop.IOLoop.instance().call_later(1, leader.mining)

    worker_thread = threading.Thread(target=miner.worker_thread)
    worker_thread.start()

    server = Application()
    server.listen(tree.current_port, '0.0.0.0')
    tornado.ioloop.IOLoop.instance().start()

    worker_thread.join()

if __name__ == '__main__':
    main()

