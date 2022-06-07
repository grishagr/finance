
template_dict={}
symbol_list={}
symbol = "s"
name = "n"
share = "6"
symbol_list[symbol] = {"name": name, "shares":share}
template_dict["symbol"] = symbol_list


for i in template_dict:
    for x in template_dict[i]:
        print(x)

        print(template_dict[i][x]["name"])
        print(template_dict[i][x]["shares"])



print(template_dict)